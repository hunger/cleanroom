#!/usr/bin/bash

FILE="${1}"

if test $(basename "${FILE}") == '__init__.py'; then
    exit 0
fi

echo "::::::::: ${1}:"
grep "import typing" "${1}" > /dev/null || echo "!!!!!!! ${1}: typing is not imported"
mypy "${1}"
