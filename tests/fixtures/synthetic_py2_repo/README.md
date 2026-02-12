# Synthetic Python 2 Repository Fixture

This fixture repository is intentionally Python 2-oriented and is used for Sprint 2
agent tests.

## Included Files

- `main.py`: print statements, raw_input, xrange
- `utils.py`: iteritems, has_key
- `io_handler.py`: print chevron, unicode literal
- `math_ops.py`: old division, long literal
- `exceptions.py`: old raise and except syntax
- `compat.py`: apply builtin
- `file_ops.py`: execfile
- `string_utils.py`: string module usage
- `network.py`: urllib2 imports
- `meta.py`: __metaclass__ syntax
- `config.py` + `helpers.py`: dependencies
- `models.py`: mixed patterns
- `cli.py`: raw_input + print statements
- `data_processor.py`: mixed complex patterns

## Pattern Coverage (19)

1. print_statement
2. print_chevron
3. dict_iteritems
4. dict_iterkeys
5. dict_itervalues
6. dict_has_key
7. xrange
8. unicode_literal
9. long_literal
10. raise_syntax
11. except_syntax
12. old_division
13. raw_input
14. apply_builtin
15. execfile_builtin
16. string_module
17. urllib_import
18. metaclass_syntax
19. future_imports (absence)

The fixture tests in `tests/` are placeholders and are not part of the project-level
pytest collection.
