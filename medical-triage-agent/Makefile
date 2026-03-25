.PHONY: install dev test deploy invoke status

## install  — install Python dependencies via uv
install:
	uv sync

## dev      — start local AgentCore development server
dev:
	uv run agentcore dev -p 8088

## test     — invoke the local agent with a demo prompt
##            (requires `make dev` running in another terminal)
test:
	uv run agentcore invoke --dev --port 8088 "A patient named Emma Johnson is experiencing recurring headaches. Can you look her up and recommend a specialist?"

## deploy   — package and deploy to AWS via AgentCore CLI
deploy:
	uv run agentcore deploy

## invoke   — invoke the deployed agent with a demo prompt
invoke:
	uv run agentcore invoke "I have a patient with chronic cough and wheezing, MRN is MRN-10234. What specialist should they see?"

## status   — show the current deployment status
status:
	uv run agentcore status
