"""Parse simple sectioned text files."""


def parse_tokens(line):
    """Return the whitespace-separated tokens in a data line."""
    return tuple(token.strip() for token in line.partition(';')[0].split())


def format_tokens(tokens, separator=' ' * 4):
    """Join tokens into a section data line."""
    return separator.join(str(token) for token in tokens)


class SectionedText:
    """Read and write text files organized in ``[SECTION]`` blocks."""

    def __init__(self):
        self.sections = {}

    def read(self, path):
        """Read sections from a text file."""
        self.sections = {}
        section_name = None

        with open(path, 'r', encoding='latin-1') as file:
            for line in file:
                text = line.partition(';')[0].strip()
                if not text:
                    continue
                if text.startswith('[') and ']' in text:
                    section_name = text[1:text.find(']')].strip().upper()
                    if section_name == 'END':
                        break
                    self.sections[section_name] = []
                elif section_name is not None:
                    self.sections[section_name].append(text)

    def write(self, path):
        """Write sections to a text file."""
        with open(path, 'w', encoding='latin-1') as file:
            for section, lines in self.sections.items():
                file.write(f'[{section}]\n')
                for line in lines:
                    file.write(f'{line}\n')
                file.write('\n')
            file.write('[END]\n')
