commands = 'search_sequences', 'select_references'

def itermodules(root=__name__):
    for command in commands:
        yield command.replace('_', '-'), \
                __import__('.'.join((root, command)), fromlist=[command])