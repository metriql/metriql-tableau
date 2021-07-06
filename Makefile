.PHONY: all build check clean dev-requirements

all: build

build: clean
	python3 setup.py sdist bdist_wheel

clean:
	rm -rf build dist

requirements:
	pip3 install -r requirements.txt
	pip3 install -r requirements-test.txt

lint:
	pylint --disable=R,C metriql-tableau

type:
	mypy --ignore-missing-imports metriql-tableau

check: build
	twine check dist/*

upload: check
	twine upload dist/*

dev-install: build
	pip3 uninstall -y metriql-tableau && pip3 install dist/metriql_tableau-*-py3-none-any.whl