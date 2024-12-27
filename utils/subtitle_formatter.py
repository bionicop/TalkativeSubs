import datetime

class SubtitleFormatter:
    @staticmethod
    def format_timestamp(seconds):
        time = datetime.timedelta(seconds=float(seconds))
        hours = int(time.total_seconds() // 3600)
        minutes = int((time.total_seconds() % 3600) // 60)
        seconds = int(time.total_seconds() % 60)
        milliseconds = int((time.total_seconds() * 1000) % 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    @staticmethod
    def format_subtitle_segment(index, start_time, end_time, text):
        return f"{index}\n{start_time} --> {end_time}\n{text}\n\n"