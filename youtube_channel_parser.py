#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер ссылок на видео с YouTube канала
Использует yt-dlp для извлечения всех видео без загрузки
"""

import argparse
import sys
import time
import logging
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import yt_dlp


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Настройка логирования"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / "parser.log"
    
    # Настройка формата логов
    log_format = '[%(asctime)s] %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Настройка логгера
    logger = logging.getLogger('youtube_parser')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Хендлер для файла
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    # Хендлер для консоли (только важные сообщения)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def print_header():
    """Вывод заголовка программы"""
    print("=" * 47)
    print("  Парсер видео с YouTube канала (yt-dlp)  ")
    print("=" * 47)
    print()


def validate_url(url: str) -> bool:
    """Проверка корректности URL YouTube канала"""
    try:
        parsed = urlparse(url)
        if 'youtube.com' not in parsed.netloc and 'youtu.be' not in parsed.netloc:
            return False
        
        # Проверка на допустимые паттерны канала
        valid_patterns = ['/@', '/channel/', '/c/', '/user/']
        return any(pattern in url for pattern in valid_patterns)
    except Exception:
        return False


def extract_channel_name(info: dict) -> str:
    """Извлечение имени канала из метаданных"""
    # Попытка получить имя канала из разных полей
    channel_name = (
        info.get('uploader') or 
        info.get('channel') or 
        info.get('uploader_id') or 
        info.get('channel_id') or 
        'unknown_channel'
    )
    
    # Очистка имени от недопустимых символов для имени файла
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        channel_name = channel_name.replace(char, '_')
    
    return channel_name


def parse_channel(channel_url: str, output_dir: Path, output_filename: str = None, 
                  verbose: bool = False, logger: logging.Logger = None) -> tuple[list, dict]:
    """
    Парсинг канала YouTube и извлечение всех ссылок на видео
    
    Returns:
        tuple: (список ссылок на видео, метаданные канала)
    """
    if logger:
        logger.info(f"Начало парсинга канала: {channel_url}")
    
    print(f"URL канала: {channel_url}")
    print("Начало парсинга...")
    print()
    
    # Шаг 1: Проверка доступности канала
    print("[1/3] Проверка доступности канала...", end=' ', flush=True)
    
    ydl_opts = {
        'quiet': not verbose,
        'no_warnings': not verbose,
        'extract_flat': 'in_playlist',  # Извлекать видео из плейлистов
        'ignoreerrors': True,  # Продолжать при ошибках отдельных видео
        'skip_download': True,
        'no_color': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Извлечение информации о канале
            info = ydl.extract_info(channel_url, download=False)
            
            if not info:
                print("✗")
                if logger:
                    logger.error("Не удалось получить информацию о канале")
                return None, None
            
            print("OK")
            if logger:
                logger.info("Канал доступен, информация получена")
            
            # Шаг 2: Извлечение списка видео
            print("[2/3] Извлечение списка видео...", end=' ', flush=True)
            
            entries = info.get('entries', [])
            
            if not entries:
                print("OK (видео не найдено)")
                if logger:
                    logger.warning("На канале нет опубликованных видео")
                return [], info
            
            print("OK")
            if logger:
                logger.info(f"Найдено видео: {len(entries)}")
            
            # Формирование списка ссылок
            video_links = []
            skipped_count = 0
            
            for entry in entries:
                try:
                    entry_type = entry.get('_type', '')
                    
                    # Если это плейлист, извлекаем видео из него
                    if entry_type == 'playlist':
                        playlist_entries = entry.get('entries', [])
                        for playlist_entry in playlist_entries:
                            video_id = playlist_entry.get('id')
                            if video_id and not video_id.startswith('UC'):  # Пропускаем channel IDs
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                                video_links.append(video_url)
                    else:
                        # Обычное видео
                        video_id = entry.get('id')
                        if video_id and not video_id.startswith('UC'):  # Пропускаем channel IDs
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            video_links.append(video_url)
                        else:
                            skipped_count += 1
                            if logger:
                                logger.warning(f"Пропущено видео без ID: {entry.get('title', 'Unknown')}")
                except Exception as e:
                    skipped_count += 1
                    if logger:
                        logger.warning(f"Ошибка обработки видео: {e}")
            
            if skipped_count > 0 and logger:
                logger.info(f"Пропущено видео: {skipped_count}")
            
            return video_links, info
            
    except yt_dlp.utils.DownloadError as e:
        print("ERROR")
        error_msg = str(e)
        if "not found" in error_msg.lower() or "unavailable" in error_msg.lower():
            print("\nОшибка: Канал не найден. Проверьте URL.")
            if logger:
                logger.error(f"Канал не найден: {channel_url}")
        else:
            print(f"\nОшибка доступа к каналу: {error_msg}")
            if logger:
                logger.error(f"Ошибка доступа: {error_msg}")
        return None, None
    
    except Exception as e:
        print("ERROR")
        print(f"\nНепредвиденная ошибка: {e}")
        if logger:
            logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)
        return None, None


def save_results(video_links: list, output_dir: Path, channel_info: dict, 
                 output_filename: str = None, logger: logging.Logger = None) -> Path:
    """Сохранение результатов в файл"""
    print("[3/3] Сохранение результатов...", end=' ', flush=True)
    
    # Создание выходной папки
    output_dir.mkdir(exist_ok=True)
    
    # Определение имени файла
    if output_filename:
        output_file = output_dir / output_filename
    else:
        channel_name = extract_channel_name(channel_info)
        output_file = output_dir / f"{channel_name}_videos.txt"
    
    try:
        # Запись в файл
        with open(output_file, 'w', encoding='utf-8') as f:
            # Записываем ссылки
            for link in video_links:
                f.write(f"{link}\n")
            
            # Добавляем метаданные
            f.write("\n---\n")
            f.write(f"Всего видео найдено: {len(video_links)}\n")
            f.write(f"Дата парсинга: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            channel_name = extract_channel_name(channel_info)
            f.write(f"Канал: {channel_name}\n")
        
        print("OK")
        if logger:
            logger.info(f"Результат сохранён: {output_file}")
        
        return output_file
        
    except Exception as e:
        print("ERROR")
        print(f"\nОшибка записи файла: {e}")
        if logger:
            logger.error(f"Ошибка записи файла: {e}", exc_info=True)
        return None


def print_summary(video_count: int, elapsed_time: float, output_file: Path):
    """Вывод итоговой статистики"""
    print()
    print("=" * 47)
    print("Результат:")
    print(f"  - Всего видео найдено: {video_count}")
    print(f"  - Время выполнения: {elapsed_time:.0f} сек")
    print(f"  - Файл сохранен: {output_file}")
    print("=" * 47)
    print()
    print("Готово!")


def main():
    """Основная функция программы"""
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(
        description='Парсер ссылок на все видео с YouTube канала',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python youtube_channel_parser.py "https://www.youtube.com/@channelname"
  python youtube_channel_parser.py "https://www.youtube.com/channel/UCxxxx" -o my_videos.txt
  python youtube_channel_parser.py "https://www.youtube.com/@channelname" --output-dir ./results
  python youtube_channel_parser.py "https://www.youtube.com/@channelname" -v
        """
    )
    
    parser.add_argument(
        'channel_url',
        help='URL канала YouTube (например: https://www.youtube.com/@channelname)'
    )
    
    parser.add_argument(
        '-o', '--output',
        dest='output_filename',
        help='Имя выходного файла (по умолчанию генерируется автоматически)'
    )
    
    parser.add_argument(
        '--output-dir',
        dest='output_dir',
        default='output',
        help='Папка для сохранения результатов (по умолчанию: output/)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Детальный вывод (включая отладочную информацию)'
    )
    
    args = parser.parse_args()
    
    # Настройка логирования
    logger = setup_logging(verbose=args.verbose)
    
    # Вывод заголовка
    print_header()
    
    # Валидация URL
    if not validate_url(args.channel_url):
        print("Ошибка: Некорректный URL канала YouTube")
        print("Поддерживаемые форматы:")
        print("  - https://www.youtube.com/@username")
        print("  - https://www.youtube.com/channel/CHANNEL_ID")
        print("  - https://www.youtube.com/c/customname")
        logger.error(f"Некорректный URL: {args.channel_url}")
        sys.exit(1)
    
    # Засекаем время начала
    start_time = time.time()
    
    # Парсинг канала
    output_dir = Path(args.output_dir)
    
    try:
        video_links, channel_info = parse_channel(
            args.channel_url,
            output_dir,
            args.output_filename,
            args.verbose,
            logger
        )
        
        if video_links is None:
            sys.exit(1)
        
        if len(video_links) == 0:
            print("\nНа канале нет опубликованных видео")
            logger.warning("Канал не содержит видео")
            sys.exit(0)
        
        # Сохранение результатов
        output_file = save_results(
            video_links,
            output_dir,
            channel_info,
            args.output_filename,
            logger
        )
        
        if not output_file:
            sys.exit(1)
        
        # Расчёт времени выполнения
        elapsed_time = time.time() - start_time
        
        # Вывод итоговой статистики
        print_summary(len(video_links), elapsed_time, output_file)
        
        logger.info(f"Парсинг завершён успешно. Видео: {len(video_links)}, Время: {elapsed_time:.2f} сек")
        
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем")
        logger.warning("Парсинг прерван пользователем (Ctrl+C)")
        sys.exit(130)
    
    except Exception as e:
        print(f"\n\nКритическая ошибка: {e}")
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
