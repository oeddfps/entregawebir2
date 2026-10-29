"""Command-line JSON boundary; no server or scraper is started."""
import argparse
import json
import os
from pathlib import Path
import sys

from pydantic import ValidationError

from .contracts import Input, Output
from .processor import process


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace only after complete serialization, so a failed run leaves no half JSON.
    text = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Clean&Process: contract JSON to evidence-backed UI data')
    parser.add_argument('input', nargs='?', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--write-schemas', type=Path)
    parser.add_argument('--interpreter', choices=['declared', 'jev'], default='declared')
    parser.add_argument('--review-recognition', choices=['off', 'lexical', 'e5'], default='off')
    parser.add_argument('--max-questions', type=int, default=32)
    parser.add_argument('--max-request-bytes', type=int, default=60000)
    args = parser.parse_args(argv)
    if args.write_schemas:
        from .presentation import Presentation
        write_json(args.write_schemas / 'input.schema.json', Input.model_json_schema())
        write_json(args.write_schemas / 'output.schema.json', Output.model_json_schema())
        write_json(args.write_schemas / 'presentation.schema.json', Presentation.model_json_schema())
        if not args.input:
            return 0
    if not args.input:
        parser.error('input JSON is required unless only exporting schemas')
    if args.output and args.output.resolve() == args.input.resolve():
        parser.error('output must not overwrite the source input')
    if args.max_questions < 1 or args.max_request_bytes < 1:
        parser.error('interpretation limits must be positive')
    try:
        payload = Input.model_validate_json(args.input.read_text(encoding='utf-8-sig'))
        interpreter = None
        if args.interpreter == 'jev':
            from .interpreters import JevClient, JevInterpreter
            env_key = 'TYPESAFE_TEST_API_KEY' if os.getenv('TYPESAFE_TEST_MODE') == '1' else 'TYPESAFE_API_KEY'
            interpreter = JevInterpreter(JevClient(os.getenv(env_key, '')),
                max_questions=args.max_questions, max_request_bytes=args.max_request_bytes)
        recognizer = None
        if args.review_recognition != 'off':
            from .review_recognition import E5Scorer, ReviewRecognizer
            recognizer = ReviewRecognizer(E5Scorer() if args.review_recognition == 'e5' else None)
        output = process(payload, interpreter=interpreter, review_recognizer=recognizer)
        if args.output:
            write_json(args.output, output.model_dump(mode='json'))
        else:
            print(output.model_dump_json(indent=2))
        return 0
    except (ValidationError, ValueError, OSError) as exc:
        if isinstance(exc, ValidationError):
            details = [{'location': list(e['loc']), 'type': e['type']} for e in exc.errors()]
        else:
            details = [{'type': type(exc).__name__}]
        print(json.dumps({'error': 'invalid_input_or_configuration', 'details': details}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
