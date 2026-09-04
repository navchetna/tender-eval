import re

from .models import ProjectSubject

SUBJECT_FORMAT = 'CODE: PROJECT NAME'
_SUBJECT_PATTERN = re.compile(r'^\s*(?P<code>[A-Z0-9][A-Z0-9_-]*)\s*:\s*(?P<name>.+?)\s*$')


def parse_subject(subject: str) -> ProjectSubject:
    match = _SUBJECT_PATTERN.match(subject)
    if not match or subject != subject.upper():
        raise ValueError(f'Malformed subject; expected all capitals in `{SUBJECT_FORMAT}` format')
    return ProjectSubject(project_code=match.group('code'), project_name=match.group('name'))


def has_valid_subject(subject: str) -> bool:
    try:
        parse_subject(subject)
        return True
    except ValueError:
        return False