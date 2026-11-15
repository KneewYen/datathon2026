.PHONY: build-WorkflowAgentFunction build-WorkflowCoordinatorFunction build-BackendApiFunction

build-WorkflowAgentFunction build-WorkflowCoordinatorFunction build-BackendApiFunction:
	python3.12 -m pip install --disable-pip-version-check --no-compile \
		--platform manylinux2014_aarch64 --implementation cp --python-version 3.12 \
		--only-binary=:all: -r requirements.txt -t "$(ARTIFACTS_DIR)"
	cp -R app "$(ARTIFACTS_DIR)/app"
	find "$(ARTIFACTS_DIR)/app" -type d -name __pycache__ -prune -exec rm -rf {} +
	find "$(ARTIFACTS_DIR)/app" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
