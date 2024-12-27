from googletrans import Translator
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

class TranslationService:
    def __init__(self):
        self.translator = Translator()
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.max_retries = 3
        self.retry_delay = 2

    def translate_subtitles(self, subtitles, source_lang, target_lang):
        """Translate subtitles in SRT format from source_lang to target_lang while preserving order."""
        try:
            segments = re.split(r'\n\n+', subtitles.strip())
            translated_segments = []
            indexed_segments = [(i, segment) for i, segment in enumerate(segments)]
            batch_size = 10
            batches = [indexed_segments[i:i + batch_size] for i in range(0, len(indexed_segments), batch_size)]
            futures = []
            for batch in batches:
                futures.append(self.executor.submit(self._translate_batch, batch, source_lang, target_lang))
            for future in as_completed(futures):
                translated_segments.extend(future.result())
            translated_segments.sort(key=lambda x: x[0])
            ordered_translated_segments = [segment[1] for segment in translated_segments]
            return '\n\n'.join(ordered_translated_segments) + '\n\n'
        except Exception as e:
            print(f"Translation failed: {str(e)}")
            return subtitles

    def _translate_batch(self, batch, source_lang, target_lang):
        """Translate a batch of subtitle segments while preserving their order."""
        translated_batch = []
        for index, segment in batch:
            lines = segment.split('\n')
            if len(lines) >= 3:
                segment_index = lines[0]
                timestamps = lines[1]
                text = '\n'.join(lines[2:])
                translated_text = self._translate_with_retry(text, source_lang, target_lang)
                translated_segment = (index, f"{segment_index}\n{timestamps}\n{translated_text}")
                translated_batch.append(translated_segment)
        return translated_batch

    def _translate_with_retry(self, text, source_lang, target_lang):
        """Attempt translation with retries."""
        for attempt in range(self.max_retries):
            try:
                translated_text = self.translator.translate(text, src=source_lang, dest=target_lang).text
                return translated_text
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Warning: Translation failed after {self.max_retries} attempts: {str(e)}")
                    return text  # Return original text if all retries fail
                time.sleep(self.retry_delay)