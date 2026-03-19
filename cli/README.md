# LLM Evaluation CLI

Command-line interface for LLM Evaluation System.

## Installation

```bash
pip install -e .
```

## Configuration

```bash
# Set server URL
llm-eval config set-server http://localhost:8000

# Set API key (if required)
llm-eval config set-api-key your-api-key

# View configuration
llm-eval config show
```

## Usage

### Dataset Management

```bash
# List datasets
llm-eval dataset list

# Create dataset
llm-eval dataset create "My Dataset" --description "Test dataset" --tags "tag1,tag2"

# Import test cases
llm-eval dataset import <dataset-id> cases.json

# Export dataset
llm-eval dataset export <dataset-id> --format json --output dataset.json

# Delete dataset
llm-eval dataset delete <dataset-id>
```

### Scoring Rules

```bash
# List rules
llm-eval rule list

# Create predefined rule
llm-eval rule create "Answer Relevancy" --type predefined --metric answer_relevancy --threshold 0.7

# Create GEval rule
llm-eval rule create "Custom Eval" --type geval --config '{"criteria": "..."}' --threshold 0.8
```

### Evaluation

```bash
# Run evaluation
llm-eval evaluate run <dataset-id> \
  --target http://your-agent-api.com/chat \
  --rules "rule-id-1,rule-id-2" \
  --wait

# List tasks
llm-eval evaluate list

# Check task status
llm-eval evaluate status <task-id>

# View results
llm-eval evaluate results <task-id>
```

### Quality Gates

```bash
# Execute gate check
llm-eval gate check <gate-id> \
  --target http://your-agent-api.com/chat \
  --rules "rule-id-1,rule-id-2"

# CI/CD webhook (returns exit code 1 on failure)
llm-eval gate webhook <gate-id> \
  --target http://your-agent-api.com/chat \
  --rules "rule-id-1,rule-id-2"
```

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
- name: Run Quality Gate
  run: |
    pip install llm-eval-cli
    llm-eval config set-server ${{ secrets.EVAL_SERVER_URL }}
    llm-eval gate webhook ${{ secrets.GATE_ID }} \
      --target ${{ secrets.AGENT_API_URL }} \
      --rules ${{ secrets.SCORING_RULES }}
```
