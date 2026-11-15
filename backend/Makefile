.PHONY: build-WorkflowAgentFunction build-WorkflowCoordinatorFunction build-BackendApiFunction

build-WorkflowAgentFunction build-WorkflowCoordinatorFunction build-BackendApiFunction:
	python3.12 -m pip install --disable-pip-version-check --no-compile -r requirements.txt -t "$(ARTIFACTS_DIR)"
	cp -R app "$(ARTIFACTS_DIR)/app"
