import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Spin, Alert } from 'antd';
import { 
  DatabaseOutlined, 
  ExperimentOutlined, 
  CheckCircleOutlined, 
  ClockCircleOutlined 
} from '@ant-design/icons';
import { reportApi, evalApi, formatDateTime } from '../services/api';
import { Line } from '@ant-design/charts';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [recentTasks, setRecentTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [statsData, tasksData] = await Promise.all([
        reportApi.getDashboardStats(),
        evalApi.listTasks({ page: 1, page_size: 5 }),
      ]);
      setStats(statsData);
      setRecentTasks(tasksData.items || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
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

  const taskColumns = [
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
      title: '通过率',
      dataIndex: ['result_summary', 'pass_rate'],
      key: 'pass_rate',
      render: (rate) => rate ? `${(rate * 100).toFixed(1)}%` : '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (date) => formatDateTime(date),
    },
  ];

  const trendConfig = {
    data: stats?.trend_data || [],
    xField: 'date',
    yField: 'tasks',
    smooth: true,
    height: 200,
    color: '#1890ff',
    point: {
      size: 4,
      shape: 'circle',
    },
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return <Alert message="加载失败" description={error} type="error" />;
  }

  return (
    <div>
      <h1>仪表盘</h1>
      
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="评测集数量"
              value={stats?.total_datasets || 0}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="评测任务总数"
              value={stats?.total_tasks || 0}
              prefix={<ExperimentOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日任务"
              value={stats?.today_tasks || 0}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="近7天通过率"
              value={stats?.recent_pass_rate ? (stats.recent_pass_rate * 100).toFixed(1) : 0}
              suffix="%"
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: stats?.recent_pass_rate >= 0.9 ? '#3f8600' : '#cf1322' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="近30天任务趋势">
            <Line {...trendConfig} />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="最近任务">
            <Table
              dataSource={recentTasks}
              columns={taskColumns}
              rowKey="id"
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
