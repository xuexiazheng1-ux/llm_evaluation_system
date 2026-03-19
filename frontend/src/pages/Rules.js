import React, { useEffect, useState } from 'react';
import {
  Table, Button, Modal, Form, Input, Select, Space, Popconfirm,
  message, Tag, Card, InputNumber
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { ruleApi, formatDateTime } from '../services/api';

const { TextArea } = Input;
const { Option } = Select;

const Rules = () => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [form] = Form.useForm();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  useEffect(() => {
    fetchRules();
  }, [pagination.current, pagination.pageSize]);

  const fetchRules = async () => {
    setLoading(true);
    try {
      const response = await ruleApi.list({
        page: pagination.current,
        page_size: pagination.pageSize,
      });
      setRules(response.items || []);
      setPagination({ ...pagination, total: response.total });
    } catch (error) {
      message.error('获取评分规则失败: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (values) => {
    try {
      // 将 config JSON 字符串解析为对象
      const data = { ...values };
      if (data.config && typeof data.config === 'string') {
        try {
          data.config = JSON.parse(data.config);
        } catch (e) {
          message.error('GEval 配置 JSON 格式错误');
          return;
        }
      }
      
      if (editingRule) {
        await ruleApi.update(editingRule.id, data);
        message.success('更新成功');
      } else {
        await ruleApi.create(data);
        message.success('创建成功');
      }
      setModalVisible(false);
      form.resetFields();
      setEditingRule(null);
      fetchRules();
    } catch (error) {
      message.error(editingRule ? '更新失败: ' : '创建失败: ' + error.message);
    }
  };

  const handleDelete = async (id) => {
    try {
      await ruleApi.delete(id);
      message.success('删除成功');
      fetchRules();
    } catch (error) {
      message.error('删除失败: ' + error.message);
    }
  };

  const handleEdit = (record) => {
    setEditingRule(record);
    form.setFieldsValue({
      name: record.name,
      rule_type: record.rule_type,
      metric_name: record.metric_name,
      threshold: record.threshold ? parseFloat(record.threshold) : undefined,
      config: record.config ? JSON.stringify(record.config, null, 2) : '',
    });
    setModalVisible(true);
  };

  const handleAdd = () => {
    setEditingRule(null);
    form.resetFields();
    setModalVisible(true);
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '类型',
      dataIndex: 'rule_type',
      key: 'rule_type',
      render: (type) => (
        <Tag color={type === 'predefined' ? 'blue' : 'green'}>
          {type === 'predefined' ? '预定义指标' : 'GEval'}
        </Tag>
      ),
    },
    {
      title: '指标名称',
      dataIndex: 'metric_name',
      key: 'metric_name',
      render: (name) => name || '-',
    },
    {
      title: '阈值',
      dataIndex: 'threshold',
      key: 'threshold',
      render: (threshold) => threshold ? `${(threshold * 100).toFixed(0)}%` : '-',
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
      width: 150,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确认删除"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const predefinedMetrics = [
    { value: 'answer_relevancy', label: 'Answer Relevancy (回答相关性)' },
    { value: 'faithfulness', label: 'Faithfulness (忠实度)' },
    { value: 'contextual_relevancy', label: 'Contextual Relevancy (上下文相关性)' },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h1>评分规则</h1>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleAdd}
        >
          新建规则
        </Button>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={rules}
          rowKey="id"
          loading={loading}
          pagination={pagination}
          onChange={(p) => setPagination({ ...pagination, current: p.current, pageSize: p.pageSize })}
        />
      </Card>

      <Modal
        title={editingRule ? '编辑评分规则' : '新建评分规则'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        width={600}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item
            name="name"
            label="规则名称"
            rules={[{ required: true, message: '请输入规则名称' }]}
          >
            <Input placeholder="如：回答质量评分" />
          </Form.Item>

          <Form.Item
            name="rule_type"
            label="规则类型"
            rules={[{ required: true, message: '请选择规则类型' }]}
          >
            <Select placeholder="选择规则类型">
              <Option value="predefined">预定义指标</Option>
              <Option value="geval">GEval (自定义)</Option>
            </Select>
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) => prevValues.rule_type !== currentValues.rule_type}
          >
            {({ getFieldValue }) => {
              const ruleType = getFieldValue('rule_type');
              
              if (ruleType === 'predefined') {
                return (
                  <Form.Item
                    name="metric_name"
                    label="选择指标"
                    rules={[{ required: true, message: '请选择指标' }]}
                  >
                    <Select placeholder="选择预定义指标">
                      {predefinedMetrics.map(m => (
                        <Option key={m.value} value={m.value}>{m.label}</Option>
                      ))}
                    </Select>
                  </Form.Item>
                );
              }
              
              if (ruleType === 'geval') {
                return (
                  <>
                    <Form.Item
                      name="config"
                      label="GEval配置 (JSON)"
                      rules={[
                        { required: true, message: '请输入GEval配置' },
                        {
                          validator: (_, value) => {
                            if (!value) return Promise.resolve();
                            try {
                              JSON.parse(value);
                              return Promise.resolve();
                            } catch (e) {
                              return Promise.reject('JSON 格式错误: ' + e.message);
                            }
                          }
                        }
                      ]}
                    >
                      <TextArea
                        rows={8}
                        placeholder={`{\n  "criteria": "评估回答是否准确且完整",\n  "evaluation_steps": [\n    "检查回答是否准确",\n    "检查回答是否完整"\n  ]\n}`}
                      />
                    </Form.Item>
                    <div style={{ marginBottom: 16, padding: 12, background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4 }}>
                      <div style={{ fontWeight: 'bold', marginBottom: 8, color: '#52c41a' }}>配置说明:</div>
                      <div style={{ fontSize: 12, color: '#666' }}>
                        <div>• criteria: 评估标准的整体描述</div>
                        <div>• evaluation_steps: 评估步骤列表（数组）</div>
                      </div>
                    </div>
                  </>
                );
              }
              
              return null;
            }}
          </Form.Item>

          <Form.Item
            name="threshold"
            label="通过阈值"
            initialValue={0.5}
          >
            <InputNumber
              min={0}
              max={1}
              step={0.1}
              style={{ width: '100%' }}
              formatter={(value) => `${(value * 100).toFixed(0)}%`}
              parser={(value) => parseFloat(value.replace('%', '')) / 100}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Rules;
