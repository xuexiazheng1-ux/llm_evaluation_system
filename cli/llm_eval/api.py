"""
API client for LLM Evaluation System
"""
import requests
from urllib.parse import urljoin

from llm_eval.config import get_api_base_url, get_headers


class APIClient:
    """API client for LLM Evaluation System"""
    
    def __init__(self):
        self.base_url = get_api_base_url()
        self.headers = get_headers()
    
    def _url(self, path):
        """Build full URL"""
        return urljoin(self.base_url + "/", "api/v1/" + path)
    
    def _request(self, method, path, **kwargs):
        """Make HTTP request"""
        url = self._url(path)
        headers = {**self.headers, **kwargs.pop("headers", {})}
        
        try:
            response = requests.request(
                method, url, headers=headers, timeout=30, **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            raise Exception(f"无法连接到服务器: {self.base_url}")
        except requests.exceptions.Timeout:
            raise Exception("请求超时")
        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
                raise Exception(error_data.get("detail", str(e)))
            except:
                raise Exception(f"HTTP错误: {e.response.status_code}")
    
    # Dataset APIs
    def list_datasets(self, page=1, page_size=20, search=None):
        """List datasets"""
        params = {"page": page, "page_size": page_size}
        if search:
            params["search"] = search
        return self._request("GET", "datasets", params=params)
    
    def get_dataset(self, dataset_id):
        """Get dataset details"""
        return self._request("GET", f"datasets/{dataset_id}")
    
    def create_dataset(self, name, description=None, tags=None):
        """Create a new dataset"""
        data = {"name": name, "description": description, "tags": tags or []}
        return self._request("POST", "datasets", json=data)
    
    def delete_dataset(self, dataset_id):
        """Delete a dataset"""
        return self._request("DELETE", f"datasets/{dataset_id}")
    
    def import_dataset(self, dataset_id, format, content):
        """Import test cases to dataset"""
        data = {"format": format, "content": content}
        return self._request("POST", f"datasets/{dataset_id}/import", json=data)
    
    def export_dataset(self, dataset_id, format="json"):
        """Export dataset"""
        return self._request("GET", f"datasets/{dataset_id}/export?format={format}")
    
    # Scoring Rule APIs
    def list_rules(self, page=1, page_size=20):
        """List scoring rules"""
        return self._request("GET", "rules", params={"page": page, "page_size": page_size})
    
    def create_rule(self, name, rule_type, metric_name=None, config=None, threshold=0.5):
        """Create a scoring rule"""
        data = {
            "name": name,
            "rule_type": rule_type,
            "metric_name": metric_name,
            "config": config or {},
            "threshold": threshold,
        }
        return self._request("POST", "rules", json=data)
    
    def delete_rule(self, rule_id):
        """Delete a scoring rule"""
        return self._request("DELETE", f"rules/{rule_id}")
    
    # Evaluation APIs
    def create_task(self, name, dataset_id, config):
        """Create an evaluation task"""
        data = {"name": name, "dataset_id": dataset_id, "config": config}
        return self._request("POST", "evaluate/tasks", json=data)
    
    def list_tasks(self, page=1, page_size=20, status=None):
        """List evaluation tasks"""
        params = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        return self._request("GET", "evaluate/tasks", params=params)
    
    def get_task(self, task_id):
        """Get task details"""
        return self._request("GET", f"evaluate/tasks/{task_id}")
    
    def get_task_status(self, task_id):
        """Get task status"""
        return self._request("GET", f"evaluate/tasks/{task_id}/status")
    
    def cancel_task(self, task_id):
        """Cancel a task"""
        return self._request("POST", f"evaluate/tasks/{task_id}/cancel")
    
    def get_task_results(self, task_id, page=1, page_size=100):
        """Get task results"""
        return self._request(
            "GET", f"evaluate/tasks/{task_id}/results",
            params={"page": page, "page_size": page_size}
        )
    
    def quick_eval(self, dataset_id, target_url, scoring_rules, target_headers=None, max_cases=10):
        """Quick evaluation (sync)"""
        data = {
            "dataset_id": dataset_id,
            "target_url": target_url,
            "scoring_rules": scoring_rules,
            "target_headers": target_headers or {},
            "max_cases": max_cases,
        }
        return self._request("POST", "evaluate/quick", json=data)
    
    # Report APIs
    def list_reports(self, page=1, page_size=20):
        """List reports"""
        return self._request("GET", "reports", params={"page": page, "page_size": page_size})
    
    def get_report(self, report_id):
        """Get report details"""
        return self._request("GET", f"reports/{report_id}")
    
    # Quality Gate APIs
    def list_gates(self, page=1, page_size=20):
        """List quality gates"""
        return self._request("GET", "gates", params={"page": page, "page_size": page_size})
    
    def create_gate(self, name, dataset_id, rules, enabled=True):
        """Create a quality gate"""
        data = {"name": name, "dataset_id": dataset_id, "rules": rules, "enabled": enabled}
        return self._request("POST", "gates", json=data)
    
    def check_gate(self, gate_id, target_url, scoring_rules, target_headers=None):
        """Execute quality gate check"""
        data = {
            "target_url": target_url,
            "scoring_rules": scoring_rules,
            "target_headers": target_headers or {},
        }
        return self._request("POST", f"gates/{gate_id}/check", json=data)
    
    def gate_webhook(self, gate_id, target_url, scoring_rules, target_headers=None):
        """Call gate webhook"""
        data = {
            "target_url": target_url,
            "scoring_rules": scoring_rules,
            "target_headers": target_headers or {},
        }
        return self._request("POST", f"gates/webhook/{gate_id}", json=data)


# Global API client instance
api_client = APIClient()
