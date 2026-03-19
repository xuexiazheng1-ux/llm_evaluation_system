"""
Main CLI entry point
"""
import click
import json
import time
import base64
from tabulate import tabulate
from colorama import init, Fore, Style

from llm_eval import __version__
from llm_eval.config import (
    load_config, save_config, set_config_value,
    get_config_value, CONFIG_FILE
)
from llm_eval.api import api_client

# Initialize colorama
init()


def print_success(message):
    """Print success message"""
    click.echo(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")


def print_error(message):
    """Print error message"""
    click.echo(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")


def print_info(message):
    """Print info message"""
    click.echo(f"{Fore.BLUE}ℹ {message}{Style.RESET_ALL}")


def print_warning(message):
    """Print warning message"""
    click.echo(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")


@click.group()
@click.version_option(version=__version__)
@click.option('--server', help='Server URL')
@click.option('--api-key', help='API key')
@click.pass_context
def cli(ctx, server, api_key):
    """LLM Evaluation System CLI"""
    ctx.ensure_object(dict)
    
    # Override config with command line options
    if server:
        set_config_value("server_url", server)
    if api_key:
        set_config_value("api_key", api_key)


# ============== Config Commands ==============

@cli.group()
def config():
    """Configuration management"""
    pass


@config.command()
@click.argument('server_url')
def set_server(server_url):
    """Set server URL"""
    set_config_value("server_url", server_url)
    print_success(f"Server URL set to: {server_url}")


@config.command()
@click.argument('api_key')
def set_api_key(api_key):
    """Set API key"""
    set_config_value("api_key", api_key)
    print_success("API key set")


@config.command()
def show():
    """Show current configuration"""
    cfg = load_config()
    click.echo("Current configuration:")
    click.echo(f"  Config file: {CONFIG_FILE}")
    click.echo(f"  Server URL: {cfg.get('server_url')}")
    click.echo(f"  API Key: {'*****' if cfg.get('api_key') else 'Not set'}")


# ============== Dataset Commands ==============

@cli.group()
def dataset():
    """Dataset management"""
    pass


@dataset.command()
@click.option('--page', '-p', default=1, help='Page number')
@click.option('--page-size', '-s', default=20, help='Page size')
@click.option('--search', help='Search keyword')
def list(page, page_size, search):
    """List datasets"""
    try:
        response = api_client.list_datasets(page, page_size, search)
        items = response.get('items', [])
        
        if not items:
            print_info("No datasets found")
            return
        
        headers = ['ID', 'Name', 'Cases', 'Version', 'Updated']
        rows = [[
            item['id'][:8],
            item['name'],
            item.get('test_case_count', 0),
            item['version'],
            item['updated_at'][:10]
        ] for item in items]
        
        click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
        click.echo(f"\nTotal: {response.get('total', 0)} datasets")
    except Exception as e:
        print_error(str(e))


@dataset.command()
@click.argument('name')
@click.option('--description', '-d', help='Dataset description')
@click.option('--tags', '-t', help='Tags (comma separated)')
def create(name, description, tags):
    """Create a new dataset"""
    try:
        tag_list = [t.strip() for t in tags.split(',')] if tags else []
        response = api_client.create_dataset(name, description, tag_list)
        print_success(f"Dataset created: {response['id']}")
    except Exception as e:
        print_error(str(e))


@dataset.command()
@click.argument('dataset_id')
def delete(dataset_id):
    """Delete a dataset"""
    try:
        api_client.delete_dataset(dataset_id)
        print_success("Dataset deleted")
    except Exception as e:
        print_error(str(e))


@dataset.command()
@click.argument('dataset_id')
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--format', '-f', type=click.Choice(['json', 'csv']), help='File format')
def import_cases(dataset_id, file_path, format):
    """Import test cases from file"""
    try:
        # Detect format from extension if not specified
        if not format:
            format = 'json' if file_path.endswith('.json') else 'csv'
        
        # Read and encode file
        with open(file_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode('utf-8')
        
        response = api_client.import_dataset(dataset_id, format, content)
        print_success(response.get('message', 'Import successful'))
    except Exception as e:
        print_error(str(e))


@dataset.command()
@click.argument('dataset_id')
@click.option('--format', '-f', type=click.Choice(['json', 'csv']), default='json')
@click.option('--output', '-o', type=click.Path(), help='Output file path')
def export(dataset_id, format, output):
    """Export dataset to file"""
    try:
        content = api_client.export_dataset(dataset_id, format)
        
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                f.write(content)
            print_success(f"Exported to: {output}")
        else:
            click.echo(content)
    except Exception as e:
        print_error(str(e))


# ============== Rule Commands ==============

@cli.group()
def rule():
    """Scoring rule management"""
    pass


@rule.command()
@click.option('--page', '-p', default=1, help='Page number')
@click.option('--page-size', '-s', default=20, help='Page size')
def list(page, page_size):
    """List scoring rules"""
    try:
        response = api_client.list_rules(page, page_size)
        items = response.get('items', [])
        
        if not items:
            print_info("No rules found")
            return
        
        headers = ['ID', 'Name', 'Type', 'Metric', 'Threshold']
        rows = [[
            item['id'][:8],
            item['name'],
            item['rule_type'],
            item.get('metric_name', '-'),
            f"{float(item.get('threshold', 0)) * 100:.0f}%"
        ] for item in items]
        
        click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
    except Exception as e:
        print_error(str(e))


@rule.command()
@click.argument('name')
@click.option('--type', 'rule_type', type=click.Choice(['predefined', 'geval']), required=True)
@click.option('--metric', help='Predefined metric name (for predefined type)')
@click.option('--threshold', default=0.5, help='Pass threshold (0-1)')
@click.option('--config', '-c', help='GEval config as JSON string (for geval type)')
def create(name, rule_type, metric, threshold, config):
    """Create a scoring rule"""
    try:
        config_dict = json.loads(config) if config else {}
        response = api_client.create_rule(name, rule_type, metric, config_dict, threshold)
        print_success(f"Rule created: {response['id']}")
    except Exception as e:
        print_error(str(e))


# ============== Evaluate Commands ==============

@cli.group()
def evaluate():
    """Evaluation execution"""
    pass


@evaluate.command()
@click.argument('dataset_id')
@click.option('--target', '-t', required=True, help='Target agent API URL')
@click.option('--rules', '-r', required=True, help='Scoring rule IDs (comma separated)')
@click.option('--headers', '-h', help='Request headers as JSON string')
@click.option('--name', '-n', help='Task name')
@click.option('--wait/--no-wait', default=True, help='Wait for completion')
def run(dataset_id, target, rules, headers, name, wait):
    """Run evaluation task"""
    try:
        rule_ids = [r.strip() for r in rules.split(',')]
        headers_dict = json.loads(headers) if headers else {}
        
        task_name = name or f"CLI-Eval-{int(time.time())}"
        config = {
            "target_url": target,
            "target_headers": headers_dict,
            "scoring_rules": rule_ids,
            "concurrency": 1,
            "timeout": 60,
        }
        
        response = api_client.create_task(task_name, dataset_id, config)
        task_id = response['id']
        print_info(f"Task created: {task_id}")
        
        if wait:
            print_info("Waiting for completion...")
            while True:
                status = api_client.get_task_status(task_id)
                if status['status'] in ['completed', 'failed', 'cancelled']:
                    break
                time.sleep(3)
            
            if status['status'] == 'completed':
                summary = status.get('result_summary', {})
                print_success("Evaluation completed!")
                click.echo(f"  Total: {summary.get('total_cases', 0)}")
                click.echo(f"  Passed: {summary.get('passed_cases', 0)}")
                click.echo(f"  Failed: {summary.get('failed_cases', 0)}")
                click.echo(f"  Pass Rate: {summary.get('pass_rate', 0) * 100:.1f}%")
            else:
                print_error(f"Task {status['status']}")
    except Exception as e:
        print_error(str(e))


@evaluate.command()
@click.option('--page', '-p', default=1, help='Page number')
@click.option('--page-size', '-s', default=20, help='Page size')
@click.option('--status', type=click.Choice(['pending', 'running', 'completed', 'failed']))
def list(page, page_size, status):
    """List evaluation tasks"""
    try:
        response = api_client.list_tasks(page, page_size, status)
        items = response.get('items', [])
        
        if not items:
            print_info("No tasks found")
            return
        
        headers = ['ID', 'Name', 'Status', 'Pass Rate', 'Created']
        rows = []
        for item in items:
            summary = item.get('result_summary', {})
            pass_rate = summary.get('pass_rate', 0) * 100
            rows.append([
                item['id'][:8],
                item['name'][:30],
                item['status'],
                f"{pass_rate:.1f}%" if pass_rate else '-',
                item['created_at'][:10]
            ])
        
        click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
    except Exception as e:
        print_error(str(e))


@evaluate.command()
@click.argument('task_id')
def status(task_id):
    """Get task status"""
    try:
        response = api_client.get_task_status(task_id)
        click.echo(f"Task ID: {task_id}")
        click.echo(f"Status: {response['status']}")
        if response.get('result_summary'):
            click.echo(f"Summary: {json.dumps(response['result_summary'], indent=2)}")
    except Exception as e:
        print_error(str(e))


@evaluate.command()
@click.argument('task_id')
def results(task_id):
    """Get task results"""
    try:
        response = api_client.get_task_results(task_id)
        items = response.get('items', [])
        
        if not items:
            print_info("No results found")
            return
        
        headers = ['Case ID', 'Score', 'Passed', 'Latency(ms)']
        rows = [[
            item['case_id'][:8],
            f"{float(item.get('overall_score', 0)):.2f}",
            '✓' if item.get('passed') else '✗',
            item.get('latency_ms', '-')
        ] for item in items]
        
        click.echo(tabulate(rows, headers=headers, tablefmt='grid'))
    except Exception as e:
        print_error(str(e))


# ============== Gate Commands ==============

@cli.group()
def gate():
    """Quality gate management"""
    pass


@gate.command()
@click.argument('gate_id')
@click.option('--target', '-t', required=True, help='Target agent API URL')
@click.option('--rules', '-r', required=True, help='Scoring rule IDs (comma separated)')
@click.option('--headers', '-h', help='Request headers as JSON string')
def check(gate_id, target, rules, headers):
    """Execute quality gate check"""
    try:
        rule_ids = [r.strip() for r in rules.split(',')]
        headers_dict = json.loads(headers) if headers else {}
        
        print_info("Running gate check...")
        response = api_client.check_gate(gate_id, target, rule_ids, headers_dict)
        
        if response.get('passed'):
            print_success("Quality gate PASSED ✓")
        else:
            print_error("Quality gate FAILED ✗")
        
        click.echo("\nDetails:")
        for detail in response.get('details', []):
            status = "✓" if detail.get('passed') else "✗"
            click.echo(f"  {status} {detail['metric']}: {detail['actual_value']:.2f} {detail['operator']} {detail['threshold']}")
    except Exception as e:
        print_error(str(e))


@gate.command()
@click.argument('gate_id')
@click.option('--target', '-t', required=True, help='Target agent API URL')
@click.option('--rules', '-r', required=True, help='Scoring rule IDs (comma separated)')
@click.option('--headers', '-h', help='Request headers as JSON string')
def webhook(gate_id, target, rules, headers):
    """Call gate webhook (for CI/CD)"""
    try:
        rule_ids = [r.strip() for r in rules.split(',')]
        headers_dict = json.loads(headers) if headers else {}
        
        response = api_client.gate_webhook(gate_id, target, rule_ids, headers_dict)
        
        if response.get('passed'):
            print_success("PASSED")
            click.echo(f"Task ID: {response.get('task_id')}")
        else:
            print_error("FAILED")
            click.echo(f"Task ID: {response.get('task_id')}")
            exit(1)
    except Exception as e:
        print_error(str(e))
        exit(1)


if __name__ == '__main__':
    cli()
