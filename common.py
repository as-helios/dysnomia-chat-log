
def read_file_to_list(filename):
    try:
        lines = []
        with open(filename, 'r') as f:
            for line in f.readlines():
                lines.append(line.strip())
        return lines
    except FileNotFoundError:
        return []