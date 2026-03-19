import React, { useEffect, useState } from 'react';
import {
  Steps, Button, Form, Select, Input, Card, Table, Tag,
  Progress, message, Space, Divider, Alert, Spin, Descriptions
} from 'antd';
import { PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { datasetApi, ruleApi, evalApi, formatDateTime } from '../services/api';
import { useSearchParams } from 'react-router-dom';

const { Step } = Steps;
const { Option } = Select;

const Evaluate = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [datasets, setDatasets] = useState([]);
  const [rules, setRules] = useState([]);
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [taskStatus, setTaskStatus] = useState(null);
  const [taskId, setTaskId] = useState(null);
  const [results, setResults] = useState([]);
  const [searchParams] = useSearchParams();

  useEffect(() => {
    fetchDatasets();
    fetchRules();
    
    // Pre-select dataset from URL
    const datasetId = searchParams.get('dataset');
    if (datasetId) {
      form.setFieldsValue({ dataset_id: datasetId });
    }
    
    // Check for rerun task config
    const rerunConfig = localStorage.getItem('rerun_task_config');
    if (rerunConfig) {
      try {
        const config = JSON.parse(rerunConfig);
        // Pre-fill form with previous task config
        form.setFieldsValue({
          dataset_id: config.dataset_id,
          name: config.name,
          target_url: config.config?.target_url,
          target_headers: config.config?.target_headers ? JSON.stringify(config.config.target_headers, null, 2) : '',
          scoring_rules: config.config?.scoring_rules,
          concurrency: config.config?.concurrency || 1,
          timeout: config.config?.timeout || 60,
        });
        message.success('已加载上次执行配置，可修改后重新执行');
        // Clear the config after loading
        localStorage.removeItem('rerun_task_config');
      } catch (e) {
        console.error('Failed to parse rerun config:', e);
      }
    }
  }, []);

  useEffect(() => {
    let interval;
    if (taskId && taskStatus === 'running') {
      interval = setInterval(checkTaskStatus, 3000);
    }
    return () => clearInterval(interval);
  }, [taskId, taskStatus]);

  const fetchDatasets = async () => {
    try {
      const response = await datasetApi.list({ page: 1, page_size: 100 });
      setDatasets(response.items || []);
    } catch (error) {
      message.error('获取评测集失败: ' + error.message);
    }
  };

  const fetchRules = async () => {
    try {
      const response = await ruleApi.list({ page: 1, page_size: 100 });
      setRules(response.items || []);
    } catch (error) {
      message.error('获取评分规则失败: ' + error.message);
    }
  };

  const checkTaskStatus = async () => {
    try {
      const status = await evalApi.getTaskStatus(taskId);
      setTaskStatus(status.status);
      
      if (status.status === 'completed' || status.status === 'failed') {
        fetchResults();
      }
    } catch (error) {
      console.error('获取任务状态失败:', error);
    }
  };

  const fetchResults = async () => {
    try {
      const response = await evalApi.getTaskResults(taskId, { page: 1, page_size: 100 });
      setResults(response.items || []);
    } catch (error) {
      message.error('获取结果失败: ' + error.message);
    }
  };

  const handleSubmit = async () => {
    try {
      // 获取所有表单字段值（包括之前步骤的）
      const allValues = form.getFieldsValue();
      
      // 调试：打印表单值
      console.log('Form values:', allValues);
      console.log('Dataset ID:', allValues.dataset_id);
      console.log('Form instance:', form);
      console.log('Form fields:', form.getFieldsValue(true));
      
      // 验证必填字段
      if (!allValues.dataset_id) {
        message.error('请选择评测集');
        setCurrentStep(0);
        return;
      }
      if (!allValues.target_url) {
        message.error('请输入目标API地址');
        setCurrentStep(1);
        return;
      }
      if (!allValues.scoring_rules || allValues.scoring_rules.length === 0) {
        message.error('请选择至少一个评分规则');
        setCurrentStep(1);
        return;
      }
      
      setLoading(true);
      
      const config = {
        target_url: allValues.target_url,
        target_headers: allValues.target_headers ? JSON.parse(allValues.target_headers) : {},
        scoring_rules: allValues.scoring_rules,
        concurrency: allValues.concurrency || 1,
        timeout: allValues.timeout || 60,
      };
      
      const response = await evalApi.createTask({
        name: allValues.name || `评测任务-${formatDateTime(new Date())}`,
        dataset_id: allValues.dataset_id,
        config,
      });
      
      setTaskId(response.id);
      setTaskStatus(response.status);
      setCurrentStep(2);
      message.success('评测任务已创建');
    } catch (error) {
      message.error('创建任务失败: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const getStatusTag = (status) => {
    const statusMap = {
      pending: { color: 'default', text: '待执行', icon: <Spin size="small" /> },
      running: { color: 'processing', text: '执行中', icon: <Spin size="small" /> },
      completed: { color: 'success', text: '已完成', icon: <CheckCircleOutlined /> },
      failed: { color: 'error', text: '失败', icon: <CloseCircleOutlined /> },
    };
    const { color, text, icon } = statusMap[status] || { color: 'default', text: status };
    return <Tag color={color} icon={icon}>{text}</Tag>;
  };

  const resultColumns = [
    {
      title: '输入',
      dataIndex: ['test_case', 'input'],
      key: 'input',
      ellipsis: true,
      width: 250,
    },
    {
      title: '期望输出',
      dataIndex: ['test_case', 'expected_output'],
      key: 'expected_output',
      ellipsis: true,
    },
    {
      title: '实际输出',
      dataIndex: 'actual_output',
      key: 'actual_output',
      ellipsis: true,
    },
    {
      title: '综合得分',
      dataIndex: 'overall_score',
      key: 'overall_score',
      render: (score) => {
        if (score === null || score === undefined) return '-';
        const numScore = typeof score === 'number' ? score : parseFloat(score);
        return isNaN(numScore) ? '-' : numScore.toFixed(2);
      },
    },
    {
      title: '状态',
      dataIndex: 'passed',
      key: 'passed',
      render: (passed, record) => {
        if (record.error_message) {
          return <Tag color="orange">错误</Tag>;
        }
        return passed ? <Tag color="success">通过</Tag> : <Tag color="error">失败</Tag>;
      },
    },
    {
      title: '耗时(ms)',
      dataIndex: 'latency_ms',
      key: 'latency_ms',
    },
  ];

  // 渲染第一步表单
  const renderStep1 = () => (
    <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
      <Form.Item
        name="dataset_id"
        label="评测集"
        rules={[{ required: true, message: '请选择评测集' }]}
      >
        <Select 
          placeholder="选择评测集" 
          style={{ width: '100%' }}
          onChange={(value) => {
            console.log('Dataset selected:', value);
            form.setFieldsValue({ dataset_id: value });
            console.log('After setFieldsValue, form values:', form.getFieldsValue());
          }}
        >
          {datasets.map(ds => (
            <Option key={ds.id} value={ds.id}>{ds.name} ({ds.test_case_count} 用例)</Option>
          ))}
        </Select>
      </Form.Item>
    </div>
  );

  // 渲染第二步表单
  const renderStep2 = () => (
    <div style={{ display: currentStep === 1 ? 'block' : 'none' }}>
      <Form.Item
        name="name"
        label="任务名称"
      >
        <Input placeholder="可选，默认为自动生成" />
      </Form.Item>
      <Form.Item
        name="target_url"
        label="目标Agent API地址"
        rules={[{ required: true, message: '请输入API地址' }]}
      >
        <Input placeholder="http://your-agent-api.com/chat" />
      </Form.Item>
      <Form.Item
        name="target_headers"
        label="请求Headers"
      >
        <Input.TextArea 
          rows={3} 
          placeholder='{"Authorization": "Bearer xxx"}'
        />
      </Form.Item>
      <Form.Item
        name="scoring_rules"
        label="评分规则"
        rules={[{ required: true, message: '请选择评分规则' }]}
      >
        <Select mode="multiple" placeholder="选择评分规则">
          {rules.map(rule => (
            <Option key={rule.id} value={rule.id}>
              {rule.name} ({rule.rule_type})
            </Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item
        name="concurrency"
        label="并发数"
        initialValue={1}
      >
        <Select>
          <Option value={1}>1</Option>
          <Option value={2}>2</Option>
          <Option value={5}>5</Option>
          <Option value={10}>10</Option>
        </Select>
      </Form.Item>
      <Form.Item
        name="timeout"
        label="超时时间(秒)"
        initialValue={60}
      >
        <Select>
          <Option value={30}>30</Option>
          <Option value={60}>60</Option>
          <Option value={120}>120</Option>
          <Option value={300}>300</Option>
        </Select>
      </Form.Item>
    </div>
  );

  const steps = [
    {
      title: '选择评测集',
      content: renderStep1(),
    },
    {
      title: '配置参数',
      content: renderStep2(),
    },
    {
      title: '执行评测',
      content: (
        <div>
          {taskStatus && (
            <Card style={{ marginBottom: 16 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>任务状态: {getStatusTag(taskStatus)}</div>
                {taskStatus === 'running' && (
                  <Progress percent={50} status="active" />
                )}
                {taskStatus === 'completed' && results.length > 0 && (
                  <Alert
                    message="评测完成"
                    description={
                      <Descriptions size="small" column={3}>
                        <Descriptions.Item label="总用例数">{results.length}</Descriptions.Item>
                        <Descriptions.Item label="通过">
                          {results.filter(r => r.passed).length}
                        </Descriptions.Item>
                        <Descriptions.Item label="失败">
                          {results.filter(r => !r.passed && !r.error_message).length}
                        </Descriptions.Item>
                      </Descriptions>
                    }
                    type="success"
                  />
                )}
              </Space>
            </Card>
          )}
          
          {results.length > 0 && (
            <Table
              columns={resultColumns}
              dataSource={results}
              rowKey="id"
              size="small"
              pagination={{ pageSize: 10 }}
            />
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <h1>执行评测</h1>
      
      <Card style={{ marginTop: 24 }}>
        <Steps current={currentStep} style={{ marginBottom: 24 }}>
          {steps.map(item => (
            <Step key={item.title} title={item.title} />
          ))}
        </Steps>

        <Form form={form} layout="vertical">
          {renderStep1()}
          {renderStep2()}
          {currentStep === 2 && steps[2].content}
        </Form>

        <Divider />

        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Button
            disabled={currentStep === 0}
            onClick={() => setCurrentStep(currentStep - 1)}
          >
            上一步
          </Button>
          <div>
            {currentStep < steps.length - 1 && (
              <Button type="primary" onClick={async () => {
                try {
                  // 验证当前步骤的表单字段
                  const fieldsToValidate = currentStep === 0 ? ['dataset_id'] : ['target_url', 'scoring_rules'];
                  await form.validateFields(fieldsToValidate);
                  setCurrentStep(currentStep + 1);
                } catch (error) {
                  // 验证失败，不切换步骤
                }
              }}>
                下一步
              </Button>
            )}
            {currentStep === steps.length - 2 && (
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleSubmit}
                loading={loading}
                style={{ marginLeft: 8 }}
              >
                开始评测
              </Button>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Evaluate;
