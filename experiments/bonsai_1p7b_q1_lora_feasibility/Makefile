.PHONY: doctor preflight probe train eval-hf build-llama export eval-q1 report bundle test

doctor:
	python -m pixie_bonsai.cli doctor
preflight:
	python -m pixie_bonsai.cli preflight-adapter
probe:
	python -m pixie_bonsai.cli memory-probe
train:
	python -m pixie_bonsai.cli train-smoke
eval-hf:
	python -m pixie_bonsai.cli eval-hf
build-llama:
	python -m pixie_bonsai.cli build-llama
export:
	python -m pixie_bonsai.cli export-gguf
eval-q1:
	python -m pixie_bonsai.cli eval-q1
report:
	python -m pixie_bonsai.cli report
bundle:
	python -m pixie_bonsai.cli bundle
test:
	python -m pytest

