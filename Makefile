VERSION = 0.1.0

.PHONY: publish publish-test version build clean

publish: version build
	twine upload dist/*

publish-test: version build
	twine upload --repository testpypi dist/*

build: clean
	python -m build

clean:
	rm -rf dist/ build/

version:
	sed -i 's/^version = "[0-9]\+\.[0-9]\+\.[0-9]\+"/version = "$(VERSION)"/' pyproject.toml
	sed -i 's/__version__ = "[0-9]\+\.[0-9]\+\.[0-9]\+"/__version__ = "$(VERSION)"/' src/horavox/cli.py
	sed -i 's|pip-[0-9]\+\.[0-9]\+\.[0-9]\+-blue|pip-$(VERSION)-blue|' README.md
