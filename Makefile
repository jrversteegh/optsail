.PHONY: all
all: build

.PHONY: test
test: packages pep8
	@echo "Running tests..."
	@. venv/bin/activate; TZ=Europe/Amsterdam pytest -v
	@echo "Done."

test_%: packages
	@. venv/bin/activate; tests/$@.py

.PHONY: prepare-dev
prepare-dev: packages
	@echo
	@echo Do:
	@echo
	@echo source venv/bin/activate
	@echo
	@echo or:
	@echo
	@echo . venv/bin/activate
	@echo
	@echo to activate the virtual environment.

.PHONY: build
build: packages
	@. venv/bin/activate; python -m build --sdist --wheel .

.PHONY: intall
install: build
	@. venv/bin/activate; pip install dist/optsail-*-py3-none-any.whl

.PHONY: pep8
pep8: packages
	@. venv/bin/activate; which flake8 >/dev/null || (echo "flake8 checker not available" && exit 1)
	@echo "Checking python code formatting (PEP8)"
	@. venv/bin/activate; flake8 optsail
	@echo "Done."

.PHONY: clean
clean:
	@echo "Cleaning up python cache..."
	@find . -type d -name __pycache__ -exec echo rm -rf {} \;
	@echo "Done."
	@echo "Removing setup directories..."
	@rm -rf build
	@rm -rf dist
	@rm -rf optsail.egg-info
	@hash -r || true
	@echo "Done."

.PHONY: distclean
distclean: clean
	@echo "Removing virtual environment..."
	@which python | grep venv >/dev/null 2>/dev/null && echo "Deactivate your virtual environment first" && exit 1 || echo "Virtual environment not active" 
	@rm -rf venv
	@echo "Done."

venv/bin/activate:
	@echo "Setting up virtual environment..."
	@hash -r || true
	@(which python3.8 >/dev/null && python3.8 -mvenv venv) || \
	   (which python3.7 >/dev/null && python3.7 -mvenv venv)
	@. venv/bin/activate; python -m pip install --upgrade pip
	@echo "Done."

.PHONY: packages
packages: venv/updated

venv/updated: venv/bin/activate requirements.txt
	@echo "Installing packages ..."
	@which gdal-config || ( echo "GDAL development files required. Do e.g. apt install libgdal-dev"; exit 1 )
	# GDAL needs to be build from source with the same version as the system installed version, so try
	# to take care of that here
	@. venv/bin/activate \
		&& pip install wheel \
		&& pip install ipython \
		&& pip install GDAL==`gdal-config --version` \
		&& pip install -r requirements.txt
	@touch venv/updated
	@echo "Done."
