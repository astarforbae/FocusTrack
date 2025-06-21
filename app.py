from flask import Flask, render_template, request, jsonify, redirect, url_for
from datetime import datetime, timedelta
import json
import os
from task import Task, FocusSession
from collections import defaultdict
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # 用于表单安全

# 数据文件路径
DATA_FILE = 'tasks.json'
SESSIONS_FILE = 'focus_sessions.json'

class TimeManager:
    def __init__(self):
        self.tasks = []
        self.focus_sessions = []
        self.data_file = DATA_FILE
        self.sessions_file = SESSIONS_FILE
        self.load_tasks()
        self.load_sessions()

    def add_task(self, title, description="", priority="中", expected_time=None, tags=None):
        task = Task(title, description, priority, expected_time=expected_time, tags=tags)
        self.tasks.append(task)
        self.save_tasks()
        return task

    def save_tasks(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump([task.to_dict() for task in self.tasks], f, ensure_ascii=False, indent=2)

    def load_tasks(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    tasks_data = json.load(f)
                    self.tasks = [Task.from_dict(task_data) for task_data in tasks_data]
            except json.JSONDecodeError:
                self.tasks = []

    def start_focus_session(self, task_id):
        session = FocusSession(task_id)
        self.focus_sessions.append(session)
        self.save_sessions()
        return session

    def end_focus_session(self, session_id):
        for session in self.focus_sessions:
            if session.id == session_id and not session.end_time:
                session.end_session()
                self.save_sessions()
                return session
        return None

    def get_sessions_by_date(self, date_str=None):
        sessions = []
        for session in self.focus_sessions:
            session_date = session.start_time.strftime("%Y-%m-%d")
            if not date_str or session_date == date_str:
                sessions.append(session)
        return sessions
    
    def get_task_total_time(self, task_id):
        """计算任务的总专注时间（秒）"""
        total_seconds = 0
        for session in self.focus_sessions:
            if session.task_id == task_id and session.end_time and not session.abandoned:
                total_seconds += session.duration
        return total_seconds

    def save_sessions(self):
        with open(self.sessions_file, "w", encoding="utf-8") as f:
            json.dump([session.to_dict() for session in self.focus_sessions], f, ensure_ascii=False, indent=2)

    def load_sessions(self):
        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    sessions_data = json.load(f)
                    self.focus_sessions = [FocusSession.from_dict(session_data) for session_data in sessions_data]
            except json.JSONDecodeError:
                self.focus_sessions = []

    def get_tasks(self):
        return self.tasks

    def get_task_by_id(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def complete_task(self, task_id):
        task = self.get_task_by_id(task_id)
        if task:
            task.status = "已完成"
            task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_tasks()
            # Rebuild index after status change
            search_index.clear()
            for task in self.tasks:
                search_index.add_task(task)
            return True
        return False

    def uncomplete_task(self, task_id):
        task = self.get_task_by_id(task_id)
        if task:
            task.status = "未完成"
            task.completed_at = None
            self.save_tasks()
            # Rebuild index after status change
            search_index.clear()
            for task in self.tasks:
                search_index.add_task(task)
            return True
        return False

    def delete_task(self, task_id):
        task = self.get_task_by_id(task_id)
        if task:
            self.tasks.remove(task)
            self.save_tasks()
            # Rebuild index after deletion
            search_index.clear()
            for task in self.tasks:
                search_index.add_task(task)
            return True
        return False

    def delete_focus_session(self, session_id):
        """删除指定的专注会话"""
        for i, session in enumerate(self.focus_sessions):
            if session.id == session_id:
                del self.focus_sessions[i]
                self.save_sessions()
                return True
        return False

manager = TimeManager()

class SearchIndex:
    def __init__(self):
        self.title_index = defaultdict(list)
        self.description_index = defaultdict(list)
        self.priority_index = defaultdict(list)
        self.status_index = defaultdict(list)
        self.tag_index = defaultdict(list)
        self.tasks = []

    def add_task(self, task):
        task_idx = len(self.tasks)
        self.tasks.append(task)
        
        # Index title words
        for word in re.findall(r'\w+', task.title.lower()):
            self.title_index[word].append(task_idx)
            
        # Index description words
        if task.description:
            for word in re.findall(r'\w+', task.description.lower()):
                self.description_index[word].append(task_idx)
                
        # Index priority
        self.priority_index[task.priority.lower()].append(task_idx)
        
        # Index status
        self.status_index[task.status.lower()].append(task_idx)
        
        # Index tags
        for tag in task.tags:
            self.tag_index[tag.lower()].append(task_idx)

    def clear(self):
        self.__init__()

    def search(self, query=None, priority=None, status=None, tag=None):
        # Start with all task indices
        result_set = set(range(len(self.tasks)))
        
        # Apply text search if query exists
        if query:
            query = query.lower()
            query_words = set(re.findall(r'\w+', query))
            
            # Get matching tasks from title and description indices
            matching_indices = set()
            for word in query_words:
                matching_indices.update(self.title_index[word])
                matching_indices.update(self.description_index[word])
                
            result_set &= matching_indices
            
        # Apply priority filter
        if priority:
            priority_matches = set(self.priority_index[priority.lower()])
            result_set &= priority_matches
            
        # Apply status filter
        if status:
            status_matches = set(self.status_index[status.lower()])
            result_set &= status_matches
            
        # Apply tag filter
        if tag:
            tag_matches = set(self.tag_index[tag.lower()])
            result_set &= tag_matches
            
        # Convert indices back to tasks
        return [self.tasks[i] for i in sorted(result_set)]

# Add search index as a global variable
search_index = SearchIndex()

# Replace @app.before_first_request with proper initialization
def initialize_index():
    search_index.clear()
    for task in manager.get_tasks():
        search_index.add_task(task)

# Initialize the index when the app starts
initialize_index()

@app.route('/')
def index():
    tasks = manager.get_tasks()
    
    # 获取查询参数
    sort_by = request.args.get('sort', 'created_at')  # 默认按创建时间排序
    sort_order = request.args.get('order', 'desc')  # 默认降序
    filter_status = request.args.get('status', '')  # 默认不过滤
    filter_tag = request.args.get('tag', '')  # 默认不过滤标签
    
    # 过滤任务
    filtered_tasks = []
    for task in tasks:
        # 状态过滤
        if filter_status and task.status != filter_status:
            continue
        
        # 标签过滤
        if filter_tag and filter_tag not in task.tags:
            continue
        
        filtered_tasks.append(task)
    
    # 排序任务
    if sort_by == 'created_at':
        filtered_tasks.sort(key=lambda x: x.created_at, reverse=(sort_order == 'desc'))
    elif sort_by == 'priority':
        priority_order = {"高": 0, "中": 1, "低": 2}
        filtered_tasks.sort(key=lambda x: priority_order.get(x.priority, 3), reverse=(sort_order == 'desc'))
    elif sort_by == 'status':
        filtered_tasks.sort(key=lambda x: x.status, reverse=(sort_order == 'desc'))
    elif sort_by == 'total_time':
        # Calculate total time for each task from focus sessions
        filtered_tasks.sort(key=lambda x: manager.get_task_total_time(x.id), reverse=(sort_order == 'desc'))
    
    # 计算总时间并格式化
    tasks_data = []
    for task in filtered_tasks:
        task_dict = task.to_dict()
        # 直接设置格式化的字符串，而不是调用方法
        task_dict['expected_time_str'] = task.get_expected_time_str()
        # Calculate total time from focus sessions
        total_time = manager.get_task_total_time(task.id)
        task_dict['total_time_str'] = task.get_total_time_str(total_time)
        tasks_data.append(task_dict)
    
    # 获取所有唯一标签
    all_tags = set()
    for task in tasks:
        all_tags.update(task.tags)
    
    return render_template('index.html', tasks=tasks_data, all_tags=sorted(all_tags))

@app.route('/add_task', methods=['POST'])
def add_task():
    title = request.form.get('title')
    description = request.form.get('description', '')
    priority = request.form.get('priority', '中')
    expected_time = request.form.get('expected_time')
    tags_str = request.form.get('tags', '')
    
    # 处理预期时间
    if expected_time:
        try:
            expected_time = int(expected_time)
        except ValueError:
            expected_time = None
    else:
        expected_time = None
    
    # 处理标签（逗号分隔的字符串）
    tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
    
    if title:
        task = manager.add_task(title, description, priority, expected_time, tags)
        # Add task to search index
        search_index.add_task(task)
        return redirect('/')
    return redirect('/')

@app.route('/complete_task/<task_id>')
def complete_task(task_id):
    manager.complete_task(task_id)
    # 获取当前的搜索参数
    search_query = request.args.get('search', '')
    priority_filter = request.args.get('priority', '')
    status_filter = request.args.get('status', '')
    tag_filter = request.args.get('tag', '')
    
    # 构建重定向URL，保持搜索参数
    redirect_url = url_for('index')
    params = []
    if search_query:
        params.append(f'search={search_query}')
    if priority_filter:
        params.append(f'priority={priority_filter}')
    if status_filter:
        params.append(f'status={status_filter}')
    if tag_filter:
        params.append(f'tag={tag_filter}')
    
    if params:
        redirect_url += '?' + '&'.join(params)
    
    return redirect(redirect_url)

@app.route('/uncomplete_task/<task_id>')
def uncomplete_task(task_id):
    manager.uncomplete_task(task_id)
    # 获取当前的搜索参数
    search_query = request.args.get('search', '')
    priority_filter = request.args.get('priority', '')
    status_filter = request.args.get('status', '')
    tag_filter = request.args.get('tag', '')
    
    # 构建重定向URL，保持搜索参数
    redirect_url = url_for('index')
    params = []
    if search_query:
        params.append(f'search={search_query}')
    if priority_filter:
        params.append(f'priority={priority_filter}')
    if status_filter:
        params.append(f'status={status_filter}')
    if tag_filter:
        params.append(f'tag={tag_filter}')
    
    if params:
        redirect_url += '?' + '&'.join(params)
    
    return redirect(redirect_url)

@app.route('/delete_task/<task_id>')
def delete_task(task_id):
    manager.delete_task(task_id)
    # 获取当前的搜索参数
    search_query = request.args.get('search', '')
    priority_filter = request.args.get('priority', '')
    status_filter = request.args.get('status', '')
    tag_filter = request.args.get('tag', '')
    
    # 构建重定向URL，保持搜索参数
    redirect_url = url_for('index')
    params = []
    if search_query:
        params.append(f'search={search_query}')
    if priority_filter:
        params.append(f'priority={priority_filter}')
    if status_filter:
        params.append(f'status={status_filter}')
    if tag_filter:
        params.append(f'tag={tag_filter}')
    
    if params:
        redirect_url += '?' + '&'.join(params)
    
    return redirect(redirect_url)

@app.route('/update_time', methods=['POST'])
def update_time():
    # This route is no longer needed as we calculate total time from focus sessions
    # But we'll keep it for backward compatibility
    return jsonify({'success': True})

@app.route('/start_timer/<task_id>', methods=['POST'])
def start_timer(task_id):
    task = manager.get_task_by_id(task_id)
    if task:
        task.timer_start = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        manager.save_tasks()
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/stop_timer/<task_id>', methods=['POST'])
def stop_timer(task_id):
    task = manager.get_task_by_id(task_id)
    if task:
        # We no longer need to update total_time here
        # Just start a focus session instead
        data = request.get_json()
        duration_seconds = data.get('duration', 0)  # 获取前端发送的计时时间（秒）
        
        # Create a focus session for this timer
        session = FocusSession(task_id)
        session.end_time = datetime.now()
        session.duration = duration_seconds
        manager.focus_sessions.append(session)
        manager.save_sessions()
        
        return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/search', methods=['GET'])
def search():
    # Get search parameters
    search_query = request.args.get('search', '')
    priority_filter = request.args.get('priority', '')
    status_filter = request.args.get('status', '')
    tag_filter = request.args.get('tag', '')
    
    # Use the search index
    filtered_tasks = search_index.search(
        query=search_query,
        priority=priority_filter,
        status=status_filter,
        tag=tag_filter
    )
    
    # Convert tasks to dictionaries with formatted time strings
    tasks_data = []
    for task in filtered_tasks:
        task_dict = task.to_dict()
        # 直接设置格式化的字符串，而不是调用方法
        task_dict['expected_time_str'] = task.get_expected_time_str()
        # Calculate total time from focus sessions
        total_time = manager.get_task_total_time(task.id)
        task_dict['total_time'] = total_time  # Add total_time for frontend
        task_dict['total_time_str'] = task.get_total_time_str(total_time)
        tasks_data.append(task_dict)
    
    return jsonify(tasks_data)

@app.route('/start_focus/<task_id>', methods=['POST'])
def start_focus(task_id):
    try:
        manager.start_focus_session(task_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/end_focus/<task_id>', methods=['POST'])
def end_focus(task_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Missing request body'}), 400
            
        elapsed_time = data.get('elapsed_time', 0)
        abandoned = data.get('abandoned', False)
        
        # 确保参数类型正确
        try:
            elapsed_time = int(elapsed_time)
            abandoned = bool(abandoned)
        except (ValueError, TypeError) as e:
            return jsonify({'success': False, 'error': 'Invalid parameter type'}), 400
            
        # 获取当前任务的活跃会话
        active_session = next((s for s in manager.focus_sessions if s.task_id == task_id and not s.end_time), None)
        if not active_session:
            return jsonify({'success': False, 'error': 'No active focus session found for task'}), 404
        
        # 设置会话放弃状态
        active_session.abandoned = abandoned
        
        # 结束会话
        session = manager.end_focus_session(active_session.id)
        
        # 如果会话没有被放弃，使用前端发送的时间更新会话时长
        if not abandoned and elapsed_time > 0:
            session.duration = elapsed_time
            manager.save_sessions()
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f'Error in end_focus: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/focus_history')
def focus_history():
    # 获取日期参数，默认为今天
    date_str = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
    
    # 获取该日期的所有专注会话
    sessions = manager.get_sessions_by_date(date_str)
    
    # 按任务ID分组并计算每个任务的专注时间
    task_times = {}
    task_sessions = {}
    
    for session in sessions:
        if session.end_time and not session.abandoned:  # 只统计已结束且未放弃的会话
            task_id = session.task_id
            if task_id not in task_times:
                task_times[task_id] = 0
                task_sessions[task_id] = []
            
            task_times[task_id] += session.duration
            task_sessions[task_id].append(session)
    
    # 获取任务详情并计算总专注时间
    tasks_data = []
    total_focus_time = 0
    
    for task_id, time_spent in task_times.items():
        task = manager.get_task_by_id(task_id)
        if task:
            task_data = task.to_dict()
            task_data['focus_time'] = time_spent
            task_data['focus_time_str'] = task.format_time(time_spent)
            task_data['sessions'] = []
            
            # 添加会话详情
            for session in task_sessions[task_id]:
                session_data = {
                    'id': session.id,
                    'start_time': session.start_time.strftime("%H:%M:%S"),
                    'end_time': session.end_time.strftime("%H:%M:%S") if session.end_time else "",
                    'duration': session.duration,
                    'duration_str': task.format_time(session.duration)
                }
                task_data['sessions'].append(session_data)
            
            tasks_data.append(task_data)
            total_focus_time += time_spent
    
    # 计算统计数据
    total_tasks = len(tasks_data)
    completed_tasks = sum(1 for task in tasks_data if task['status'] == '已完成')
    
    # 格式化总专注时间
    if tasks_data:
        total_focus_time_str = Task.format_time(total_focus_time)
    else:
        total_focus_time_str = "00:00:00"
    
    # 准备图表数据
    chart_data = []
    for task in tasks_data:
        chart_data.append({
            'task': task['title'],
            'time': task['focus_time'],
            'color': f"hsl({hash(task['id']) % 360}, 70%, 50%)"  # 生成一个基于任务ID的颜色
        })
    
    # 准备时间轴数据
    timeline_data = []
    for task in tasks_data:
        for session in task['sessions']:
            if 'start_time' in session and 'end_time' in session and session['end_time']:
                try:
                    start = datetime.strptime(date_str + " " + session['start_time'], "%Y-%m-%d %H:%M:%S")
                    end = datetime.strptime(date_str + " " + session['end_time'], "%Y-%m-%d %H:%M:%S")
                    
                    # 处理跨日的情况
                    if end < start:
                        end = end + timedelta(days=1)
                    
                    timeline_data.append({
                        'task_id': task['id'],
                        'task_title': task['title'],
                        'start': start.strftime("%Y-%m-%d %H:%M:%S"),
                        'end': end.strftime("%Y-%m-%d %H:%M:%S"),
                        'duration': session['duration'],
                        'color': f"hsl({hash(task['id']) % 360}, 70%, 50%)"
                    })
                except (ValueError, TypeError) as e:
                    app.logger.error(f"Error processing session: {e}")
                    # 跳过有问题的会话
                    continue
    
    # 确保所有数据都是可序列化的
    chart_data_json = json.dumps(chart_data)
    timeline_data_json = json.dumps(timeline_data)
    
    return render_template('focus_history.html', 
                          date=date_str,
                          tasks=tasks_data,
                          total_focus_time=total_focus_time_str,
                          total_tasks=total_tasks,
                          completed_tasks=completed_tasks,
                          chart_data=chart_data_json,
                          timeline_data=timeline_data_json)

@app.route('/edit_task/<task_id>', methods=['POST'])
def edit_task():
    task_id = request.form.get('id')
    task = manager.get_task_by_id(task_id)
    if task:
        task.title = request.form.get('title')
        task.description = request.form.get('description', '')
        task.priority = request.form.get('priority', '中')
        
        expected_time = request.form.get('expected_time')
        if expected_time and expected_time.isdigit():
            task.expected_time = int(expected_time)
        else:
            task.expected_time = None
        
        # 处理标签
        tags = request.form.getlist('tags')
        task.tags = [tag.strip() for tag in tags if tag.strip()]
        
        manager.save_tasks()
        
        # 更新搜索索引
        search_index.update_task(task)
        
        return redirect(url_for('index'))
    return redirect(url_for('index'))

@app.route('/delete_focus_session/<session_id>', methods=['POST'])
def delete_focus_session(session_id):
    """删除专注会话的路由"""
    if manager.delete_focus_session(session_id):
        # 获取当前的日期参数，以便重定向回同一天的历史记录
        date_str = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
        return jsonify({'success': True, 'redirect': f'/focus_history?date={date_str}'})
    return jsonify({'success': False, 'error': '找不到指定的专注会话'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12347, debug=True)