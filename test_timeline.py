import json
import os
import unittest
from datetime import datetime, timedelta

from app import app, manager

class TestTimeline(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.app = app.test_client()

    def test_timeline_data_complete(self):
        """测试时间轴详细视图是否获取所有会话数据而不仅仅是当天的数据"""
        # 获取时间轴页面，这将触发/timeline路由
        response = self.app.get('/timeline')
        
        # 确认请求成功
        self.assertEqual(response.status_code, 200)
        
        # 从HTML中提取timeline_data
        html_content = response.data.decode('utf-8')
        start_marker = "timelineData = JSON.parse('"
        end_marker = "');"
        start_index = html_content.find(start_marker) + len(start_marker)
        end_index = html_content.find(end_marker, start_index)
        
        # 提取并解析JSON数据
        if start_index > -1 and end_index > -1:
            json_str = html_content[start_index:end_index]
            timeline_data = json.loads(json_str)
            
            # 确认数据不为空
            self.assertTrue(len(timeline_data) > 0, "时间轴数据应该不为空")
            
            # 获取manager中的所有专注会话
            all_sessions = manager.focus_sessions
            completed_sessions = [s for s in all_sessions if s.end_time and not s.abandoned]
            
            # 检查时间轴数据数量是否与已完成专注会话数量一致
            self.assertEqual(
                len(timeline_data), 
                len(completed_sessions), 
                f"时间轴数据条数({len(timeline_data)})应与已完成专注会话数({len(completed_sessions)})一致"
            )
            
            # 检查是否包含多个日期的数据
            dates = set()
            for item in timeline_data:
                session_date = item['start'].split(' ')[0]  # 提取日期部分
                dates.add(session_date)
                
            self.assertTrue(
                len(dates) > 1 or len(timeline_data) == len(completed_sessions),
                f"时间轴应该包含多个日期的数据(检测到{len(dates)}个日期)，或者所有专注会话都在同一天"
            )
        else:
            self.fail("在页面中未找到时间轴数据")

if __name__ == '__main__':
    unittest.main() 