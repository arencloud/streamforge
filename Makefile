.PHONY: validate test render security
MODE ?= all
validate:
	helm lint charts/streamforge
	python3 scripts/validate.py -f environments/example/values.yaml
	python3 scripts/scan-secrets.py
	python3 scripts/check-public.py
	python3 scripts/test-publication-guards.py
	python3 scripts/check-docs.py
	python3 scripts/check-vault-layout.py
	python3 scripts/validate-dashboard.py
	python3 scripts/validate-edge.py
test: validate
	mvn -B -ntp -f order-dashboard/pom.xml verify
	mvn -B -ntp -f camel-s3/pom.xml verify
	mvn -B -ntp -f camel-connect/pom.xml verify
render:
	helm template streamforge charts/streamforge -n streamforge -f environments/example/values.yaml -f environments/example/$(MODE).yaml

# Requires the pinned Gitleaks binary on PATH; never reads Vault.
security:
	python3 scripts/check-sensitive-data.py --history
	python3 scripts/check-public.py --history
