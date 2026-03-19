import React, { useEffect, useState } from 'react';
import {
  Table, Tag, Button, Space, Popconfirm, message, Card,
  Descriptions, Drawer, Progress, Collapse, List, Typography, Badge
} from 'antd';
import {
  EyeOutlined, StopOutlined, ReloadOutlined,
  DownloadOutlined, PlayCircleOutlined, HistoryOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { evalApi, reportApi, formatDateTime } from '../services/api';

const Tasks = () => {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [results, setResults] = useState([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [historyVisible, setHistoryVisible] = useState(false);
  const [taskHistory, setTaskHistory] = useState([]);

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 5000); // Auto refresh every 5s
    return () => clearInterval(interval);
  }, [pagination.current, pagination.pageSize]);

  const fetchTasks = async () => {
    try {
      const response = await evalApi.listTasks({
        page: pagination.current,
        page_size: pagination.pageSize,
      });
      setTasks(response.items || []);
      setPagination({ ...pagination, total: response.total });
    } catch (error) {
      console.error('获取任务列表失败:', error);
    }
  };

  const fetchTaskDetail = async (task) => {
    try {
      const detail = await evalApi.getTask(task.id);
      setSelectedTask(detail);
      
      if (detail.status === 'completed') {
        // 使用原始 fetch 获取数据
        const response = await fetch(`/api/v1/evaluate/tasks/${task.id}/results?page=1&page_size=100`);
        const rawData = await response.json();
        console.log('Raw API Response:', rawData);
        console.log('Raw first item:', rawData.items?.[0]);
        console.log('Raw actual_output type:', typeof rawData.items?.[0]?.actual_output);
        console.log('Raw actual_output value:', rawData.items?.[0]?.actual_output);
        
        // 直接使用原始数据
        setResults(rawData.items || []);
      }
      
      setDetailVisible(true);
    } catch (error) {
      message.error('获取任务详情失败: ' + error.message);
    }
  };

  const handleCancel = async (id) => {
    try {
      await evalApi.cancelTask(id);
      message.success('任务已取消');
      fetchTasks();
    } catch (error) {
      message.error('取消失败: ' + error.message);
    }
  };

  const handleDownloadReport = async (taskId) => {
    try {
      const response = await reportApi.download(taskId, 'json');
      const blob = new Blob([JSON.stringify(response, null, 2)], {
        type: 'application/json'
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `report_${taskId}.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      message.error('下载报告失败: ' + error.message);
    }
  };

  // 重新执行任务 - 跳转到评测页面并预填充配置
  const handleRerunTask = (task) => {
    // 将任务配置存储到 localStorage，评测页面会读取
    const taskConfig = {
      dataset_id: task.dataset_id,
      name: `${task.name} (重跑)`,
      config: task.config,
    };
    localStorage.setItem('rerun_task_config', JSON.stringify(taskConfig));
    navigate('/evaluate');
    message.success('已跳转到评测页面，配置已自动填充');
  };

  // 查看任务执行历史（同一评测集的历史执行记录）
  const handleViewHistory = (task) => {
    // 找到同一评测集的所有任务
    const history = tasks
      .filter(t => t.dataset_id === task.dataset_id)
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    setTaskHistory(history);
    setHistoryVisible(true);
  };

  const getStatusTag = (status) => {
    const statusMap = {
      pending: { color: 'default', text: '待执行' },
      running: { color: 'processing', text: '执行中' },
      completed: { color: 'success', text: '已完成' },
      failed: { color: 'error', text: '失败' },
      cancelled: { color: 'warning', text: '已取消' },
    };
    const { color, text } = statusMap[status] || { color: 'default', text: status };
    return <Tag color={color}>{text}</Tag>;
  };

  const columns = [
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: getStatusTag,
    },
    {
      title: '进度',
      key: 'progress',
      render: (_, record) => {
        const summary = record.result_summary || {};
        if (record.status === 'running') {
          return <Progress percent={50} size="small" status="active" />;
        }
        if (record.status === 'completed') {
          const passRate = summary.pass_rate || 0;
          return (
            <Progress
              percent={Math.round(passRate * 100)}
              size="small"
              status={passRate >= 0.9 ? 'success' : 'exception'}
              format={(percent) => `${percent}%通过`}
            />
          );
        }
        return '-';
      },
    },
    {
      title: '用例数',
      key: 'case_count',
      render: (_, record) => {
        const summary = record.result_summary || {};
        return summary.total_cases || '-';
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date) => formatDateTime(date),
    },
    {
      title: '操作',
      key: 'action',
      width: 300,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => fetchTaskDetail(record)}
          >
            详情
          </Button>
          <Button
            type="link"
            icon={<PlayCircleOutlined />}
            onClick={() => handleRerunTask(record)}
          >
            重跑
          </Button>
          <Button
            type="link"
            icon={<HistoryOutlined />}
            onClick={() => handleViewHistory(record)}
          >
            历史
          </Button>
          {record.status === 'running' && (
            <Popconfirm
              title="确认取消"
              onConfirm={() => handleCancel(record.id)}
            >
              <Button type="link" danger icon={<StopOutlined />}>取消</Button>
            </Popconfirm>
          )}
          {record.status === 'completed' && (
            <Button
              type="link"
              icon={<DownloadOutlined />}
              onClick={() => handleDownloadReport(record.id)}
            >
              报告
            </Button>
          )}
        </Space>
      ),
    },
  ];

  const { Panel } = Collapse;
  const { Text, Paragraph } = Typography;

  // 渲染详细评估结果
  const renderExpandedRow = (record) => {
    const metrics = record.metrics || {};
    const metricEntries = Object.entries(metrics);
    
    if (metricEntries.length === 0) {
      return <div style={{ padding: 16 }}>暂无详细评估数据</div>;
    }

    return (
      <div style={{ padding: 16, background: '#fafafa' }}>
        <h4 style={{ marginBottom: 16 }}>详细评估指标</h4>
        <Collapse accordion>
          {metricEntries.map(([metricName, metricData], index) => (
            <Panel 
              header={
                <Space>
                  <Badge 
                    status={metricData.passed ? 'success' : 'error'} 
                    text={metricName}
                  />
                  <Tag color={metricData.score >= 0.7 ? 'success' : metricData.score >= 0.4 ? 'warning' : 'error'}>
                    得分: {(metricData.score * 100).toFixed(1)}%
                  </Tag>
                </Space>
              }
              key={index}
            >
              <div style={{ padding: '0 16px 16px' }}>
                {/* 评估说明 */}
                <div style={{ marginBottom: 12 }}>
                  <Text strong>评估说明：</Text>
                  <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
                    {metricData.reason || '暂无详细说明'}
                  </Paragraph>
                </div>
                
                {/* 优化建议 */}
                {metricData.suggestions && metricData.suggestions.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Text strong style={{ color: '#1890ff' }}>
                      优化建议：
                    </Text>
                    <List
                      size="small"
                      style={{ marginTop: 8 }}
                      dataSource={metricData.suggestions}
                      renderItem={(item, idx) => (
                        <List.Item>
                          <Text>{idx + 1}. {item}</Text>
                        </List.Item>
                      )}
                    />
                  </div>
                )}
                
                {/* 原始数据（调试用，可折叠） */}
                {metricData.raw_data && (
                  <div style={{ marginTop: 12 }}>
                    <Collapse ghost>
                      <Panel header="原始评估数据" key="raw">
                        <pre style={{ fontSize: 12, background: '#f0f0f0', padding: 8 }}>
                          {JSON.stringify(metricData.raw_data, null, 2)}
                        </pre>
                      </Panel>
                    </Collapse>
                  </div>
                )}
              </div>
            </Panel>
          ))}
        </Collapse>
      </div>
    );
  };

  const resultColumns = [
    {
      title: '输入',
      dataIndex: ['test_case', 'input'],
      key: 'input',
      ellipsis: true,
      width: 200,
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
      render: (text) => {
        if (!text) return '-';
        // 移除 <think> 标签及其内容
        const cleaned = text.replace(/<think>[\s\S]*?<\/think>/g, '').trim();
        return cleaned || '-';
      },
    },
    {
      title: '得分',
      dataIndex: 'overall_score',
      key: 'overall_score',
      render: (score) => {
        if (score === null || score === undefined) return '-';
        const numScore = typeof score === 'number' ? score : parseFloat(score);
        return isNaN(numScore) ? '-' : numScore.toFixed(2);
      },
      width: 80,
    },
    {
      title: '状态',
      dataIndex: 'passed',
      key: 'passed',
      render: (passed, record) => {
        if (record.error_message) return <Tag color="orange">错误</Tag>;
        return passed ? <Tag color="success">通过</Tag> : <Tag color="error">失败</Tag>;
      },
      width: 80,
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h1>评测任务</h1>
        <Button icon={<ReloadOutlined />} onClick={fetchTasks}>刷新</Button>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          loading={loading}
          pagination={pagination}
          onChange={(p) => setPagination({ ...pagination, current: p.current, pageSize: p.pageSize })}
        />
      </Card>

      <Drawer
        title="任务详情"
        width={900}
        open={detailVisible}
        onClose={() => setDetailVisible(false)}
      >
        {selectedTask && (
          <>
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="任务ID">{selectedTask.id}</Descriptions.Item>
              <Descriptions.Item label="任务名称">{selectedTask.name}</Descriptions.Item>
              <Descriptions.Item label="状态">
                {getStatusTag(selectedTask.status)}
              </Descriptions.Item>
              <Descriptions.Item label="评测集">
                {selectedTask.dataset?.name}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {formatDateTime(selectedTask.created_at)}
              </Descriptions.Item>
              <Descriptions.Item label="完成时间">
                {selectedTask.completed_at
                  ? formatDateTime(selectedTask.completed_at)
                  : '-'}
              </Descriptions.Item>
            </Descriptions>

            {selectedTask.result_summary && (
              <Descriptions bordered column={4} size="small" style={{ marginTop: 16 }}>
                <Descriptions.Item label="总用例数">
                  {selectedTask.result_summary.total_cases}
                </Descriptions.Item>
                <Descriptions.Item label="通过">
                  {selectedTask.result_summary.passed_cases}
                </Descriptions.Item>
                <Descriptions.Item label="失败">
                  {selectedTask.result_summary.failed_cases}
                </Descriptions.Item>
                <Descriptions.Item label="错误">
                  {selectedTask.result_summary.error_cases || 0}
                </Descriptions.Item>
              </Descriptions>
            )}

            {results.length > 0 && (
              <>
                <h3 style={{ marginTop: 24 }}>详细结果</h3>
                <Table
                  columns={resultColumns}
                  dataSource={results}
                  rowKey="id"
                  size="small"
                  pagination={{ pageSize: 10, position: ['bottomCenter'] }}
                  expandable={{
                    expandedRowRender: renderExpandedRow,
                    rowExpandable: (record) => record.metrics && Object.keys(record.metrics).length > 0,
                  }}
                />
              </>
            )}
          </>
        )}
      </Drawer>

      {/* 历史记录 Drawer */}
      <Drawer
        title="执行历史"
        width={700}
        open={historyVisible}
        onClose={() => setHistoryVisible(false)}
      >
        <Table
          columns={[
            {
              title: '执行时间',
              dataIndex: 'created_at',
              key: 'created_at',
              render: (date) => formatDateTime(date),
              width: 180,
            },
            {
              title: '任务名称',
              dataIndex: 'name',
              key: 'name',
              ellipsis: true,
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              render: getStatusTag,
              width: 100,
            },
            {
              title: '通过率',
              key: 'pass_rate',
              render: (_, record) => {
                const rate = record.result_summary?.pass_rate;
                return rate !== undefined ? `${(rate * 100).toFixed(1)}%` : '-';
              },
              width: 100,
            },
            {
              title: '操作',
              key: 'action',
              render: (_, record) => (
                <Button
                  type="link"
                  size="small"
                  onClick={() => {
                    setHistoryVisible(false);
                    fetchTaskDetail(record);
                  }}
                >
                  查看
                </Button>
              ),
              width: 80,
            },
          ]}
          dataSource={taskHistory}
          rowKey="id"
          size="small"
          pagination={false}
        />
      </Drawer>
    </div>
  );
};

export default Tasks;
