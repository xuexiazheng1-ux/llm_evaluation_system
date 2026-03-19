import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Layout, Menu, theme } from 'antd';
import {
  DashboardOutlined,
  DatabaseOutlined,
  PlayCircleOutlined,
  FileTextOutlined,
  SettingOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons';

import Dashboard from './pages/Dashboard';
import Datasets from './pages/Datasets';
import Rules from './pages/Rules';
import Evaluate from './pages/Evaluate';
import Tasks from './pages/Tasks';

const { Header, Sider, Content } = Layout;

const App = () => {
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: <Link to="/">仪表盘</Link>,
    },
    {
      key: '/datasets',
      icon: <DatabaseOutlined />,
      label: <Link to="/datasets">评测集</Link>,
    },
    {
      key: '/rules',
      icon: <SettingOutlined />,
      label: <Link to="/rules">评分规则</Link>,
    },
    {
      key: '/evaluate',
      icon: <PlayCircleOutlined />,
      label: <Link to="/evaluate">执行评测</Link>,
    },
    {
      key: '/tasks',
      icon: <UnorderedListOutlined />,
      label: <Link to="/tasks">评测任务</Link>,
    },
  ];

  return (
    <Router>
      <Layout style={{ minHeight: '100vh' }}>
        <Header style={{ display: 'flex', alignItems: 'center', background: '#001529' }}>
          <div style={{ color: 'white', fontSize: '18px', fontWeight: 'bold' }}>
            LLM评测系统
          </div>
        </Header>
        <Layout>
          <Sider width={200} style={{ background: colorBgContainer }}>
            <Menu
              mode="inline"
              defaultSelectedKeys={['/']}
              style={{ height: '100%', borderRight: 0 }}
              items={menuItems}
            />
          </Sider>
          <Layout style={{ padding: '24px' }}>
            <Content
              style={{
                padding: 24,
                margin: 0,
                minHeight: 280,
                background: colorBgContainer,
                borderRadius: borderRadiusLG,
              }}
            >
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/datasets" element={<Datasets />} />
                <Route path="/rules" element={<Rules />} />
                <Route path="/evaluate" element={<Evaluate />} />
                <Route path="/tasks" element={<Tasks />} />
              </Routes>
            </Content>
          </Layout>
        </Layout>
      </Layout>
    </Router>
  );
};

export default App;
