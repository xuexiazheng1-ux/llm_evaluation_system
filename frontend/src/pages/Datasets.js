import React, { useEffect, useState } from 'react';
import {
  Table, Button, Modal, Form, Input, Tag, Space, Popconfirm,
  message, Upload, Drawer, Card, Descriptions, Tabs
} from 'antd';
import {
  PlusOutlined, UploadOutlined, DownloadOutlined,
  EditOutlined, DeleteOutlined, PlayCircleOutlined,
  FileTextOutlined
} from '@ant-design/icons';
import { datasetApi, formatDateTime } from '../services/api';
import { useNavigate } from 'react-router-dom';

const { TextArea } = Input;
const { TabPane } = Tabs;

const Datasets = () => {
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [form] = Form.useForm();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const navigate = useNavigate();

  useEffect(() => {
    fetchDatasets();
  }, [pagination.current, pagination.pageSize]);

  const fetchDatasets = async () => {
    setLoading(true);
    try {
      const response = await datasetApi.list({
        page: pagination.current,
        page_size: pagination.pageSize,
      });
      setDatasets(response.items || []);
      setPagination({ ...pagination, total: response.total });
    } catch (error) {
      message.error('获取评测集失败: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (values) => {
    try {
      // 将逗号分隔的标签字符串转换为数组
      const data = {
        ...values,
        tags: values.tags ? values.tags.split(',').map(tag => tag.trim()).filter(tag => tag) : []
      };
      await datasetApi.create(data);
      message.success('创建成功');
      setModalVisible(false);
      form.resetFields();
      fetchDatasets();
    } catch (error) {
      message.error('创建失败: ' + error.message);
    }
  };

  const handleDelete = async (id) => {
    try {
      await datasetApi.delete(id);
      message.success('删除成功');
      fetchDatasets();
    } catch (error) {
      message.error('删除失败: ' + error.message);
    }
  };

  const handleViewDetail = async (record) => {
    try {
      const detail = await datasetApi.get(record.id);
      setSelectedDataset(detail);
      setDetailVisible(true);
    } catch (error) {
      message.error('获取详情失败: ' + error.message);
    }
  };

  const handleImport = async (file, datasetId) => {
    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const content = btoa(e.target.result);
        const format = file.name.endsWith('.json') ? 'json' : 'csv';
        await datasetApi.import(datasetId, { format, content });
        message.success('导入成功');
        handleViewDetail({ id: datasetId });
      } catch (error) {
        message.error('导入失败: ' + error.message);
      }
    };
    reader.readAsBinaryString(file);
    return false;
  };

  const handleExport = async (datasetId, format) => {
    try {
      const response = await datasetApi.export(datasetId, format);
      const blob = new Blob([response], {
        type: format === 'json' ? 'application/json' : 'text/csv'
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `dataset_${datasetId}.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      message.error('导出失败: ' + error.message);
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '用例数',
      dataIndex: 'test_case_count',
      key: 'test_case_count',
      width: 100,
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 80,
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      render: (tags) => (
        <>
          {tags?.map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (date) => formatDateTime(date),
    },
    {
      title: '操作',
      key: 'action',
      width: 250,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<FileTextOutlined />}
            onClick={() => handleViewDetail(record)}
          >
            详情
          </Button>
          <Button
            type="link"
            icon={<PlayCircleOutlined />}
            onClick={() => navigate(`/evaluate?dataset=${record.id}`)}
          >
            评测
          </Button>
          <Upload
            beforeUpload={(file) => handleImport(file, record.id)}
            showUploadList={false}
          >
            <Button type="link" icon={<UploadOutlined />}>导入</Button>
          </Upload>
          <Popconfirm
            title="确认删除"
            description="删除后将无法恢复，是否继续？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <h1>评测集管理</h1>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalVisible(true)}
        >
          新建评测集
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={datasets}
        rowKey="id"
        loading={loading}
        pagination={pagination}
        onChange={(p) => setPagination({ ...pagination, current: p.current, pageSize: p.pageSize })}
      />

      <Modal
        title="新建评测集"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} onFinish={handleCreate} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={3} />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Input placeholder="用逗号分隔，如: 客服,意图识别" />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title="评测集详情"
        width={800}
        open={detailVisible}
        onClose={() => setDetailVisible(false)}
      >
        {selectedDataset && (
          <Tabs defaultActiveKey="1">
            <TabPane tab="基本信息" key="1">
              <Descriptions bordered column={1}>
                <Descriptions.Item label="名称">{selectedDataset.name}</Descriptions.Item>
                <Descriptions.Item label="描述">{selectedDataset.description}</Descriptions.Item>
                <Descriptions.Item label="版本">{selectedDataset.version}</Descriptions.Item>
                <Descriptions.Item label="标签">
                  {selectedDataset.tags?.map(tag => <Tag key={tag}>{tag}</Tag>)}
                </Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  {formatDateTime(selectedDataset.created_at)}
                </Descriptions.Item>
              </Descriptions>
              <div style={{ marginTop: 16 }}>
                <Button
                  icon={<DownloadOutlined />}
                  onClick={() => handleExport(selectedDataset.id, 'json')}
                  style={{ marginRight: 8 }}
                >
                  导出JSON
                </Button>
                <Button
                  icon={<DownloadOutlined />}
                  onClick={() => handleExport(selectedDataset.id, 'csv')}
                >
                  导出CSV
                </Button>
              </div>
            </TabPane>
            <TabPane tab={`测试用例 (${selectedDataset.test_cases?.length || 0})`} key="2">
              <div style={{ marginBottom: 16 }}>
                <Upload
                  beforeUpload={(file) => handleImport(file, selectedDataset.id)}
                  showUploadList={false}
                >
                  <Button icon={<UploadOutlined />}>导入测试用例</Button>
                </Upload>
                <span style={{ marginLeft: 8, color: '#999', fontSize: 12 }}>
                  支持 JSON 或 CSV 格式
                </span>
              </div>
              <Table
                dataSource={selectedDataset.test_cases}
                rowKey="id"
                size="small"
                pagination={{ pageSize: 10 }}
                columns={[
                  {
                    title: '输入',
                    dataIndex: 'input',
                    ellipsis: true,
                    width: 300,
                  },
                  {
                    title: '期望输出',
                    dataIndex: 'expected_output',
                    ellipsis: true,
                  },
                ]}
              />
            </TabPane>
          </Tabs>
        )}
      </Drawer>
    </div>
  );
};

export default Datasets;
