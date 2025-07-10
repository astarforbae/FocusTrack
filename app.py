from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime, timedelta
import json
import os
from task import Task, FocusSession
from collections import defaultdict
import re
import uuid
import copy
import time

app = Flask(__name__)
app.secret_key = 'time_manager_secret_key'
app.config['SECRET_KEY'] = 'your-secret-key-here'  # 用于表单安全

# 添加自定义过滤器，用于将换行符转换为HTML的<br>标签
@app.template_filter('nl2br')
def nl2br_filter(text):
    if not text:
        return ""
    return text.replace('\n', '<br>')

# 数据文件路径
DATA_FILE = 'tasks.json'
SESSIONS_FILE = 'focus_sessions.json'

class TimeManager:
    def __init__(self):
        self.tasks = []
        self.focus_sessions = []
        self.data_file = DATA_FILE
        self.sessions_file = SESSIONS_FILE
        self.tasks_hash = None  # 添加哈希值用于检测更改
        self.sessions_hash = None  # 添加哈希值用于检测更改
        self.load_tasks()
        self.load_sessions()

    def add_task(self, title, description="", priority="中", expected_time=None, tags=None):
        task = Task(title, description, priority, expected_time=expected_time, tags=tags)
        self.tasks.append(task)
        self.save_tasks()
        return task

    def save_tasks(self):
        # 生成当前任务数据的哈希值
        tasks_data = [task.to_dict() for task in self.tasks]
        current_hash = hash(json.dumps(tasks_data, sort_keys=True))
        
        # 只有当哈希值不同时（数据有变化）才写入文件
        if current_hash != self.tasks_hash:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(tasks_data, f, ensure_ascii=False, indent=2)
            self.tasks_hash = current_hash

    def load_tasks(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    tasks_data = json.load(f)
                    self.tasks = [Task.from_dict(task_data) for task_data in tasks_data]
                    # 初始化哈希值
                    self.tasks_hash = hash(json.dumps(tasks_data, sort_keys=True))
            except json.JSONDecodeError:
                self.tasks = []
                self.tasks_hash = hash("[]")

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
        # 初始化会话日期缓存，如果不存在
        if not hasattr(self, 'sessions_by_date_cache'):
            self.sessions_by_date_cache = {}
            self.sessions_date_cache_hash = self.sessions_hash
            
        # 检查缓存是否仍然有效
        if self.sessions_date_cache_hash != self.sessions_hash:
            # 如果会话数据已更改，则清除缓存
            self.sessions_by_date_cache = {}
            self.sessions_date_cache_hash = self.sessions_hash
            
        # 使用缓存键
        cache_key = date_str or "all"
        
        # 尝试从缓存获取
        if cache_key in self.sessions_by_date_cache:
            return self.sessions_by_date_cache[cache_key]
            
        # 计算结果
        sessions = []
        for session in self.focus_sessions:
            session_date = session.start_time.strftime("%Y-%m-%d")
            if not date_str or session_date == date_str:
                sessions.append(session)
        
        # 存入缓存
        self.sessions_by_date_cache[cache_key] = sessions
        return sessions
    
    def get_task_total_time(self, task_id):
        """计算任务的总专注时间（秒）"""
        # 初始化时间缓存，如果不存在
        if not hasattr(self, 'task_time_cache'):
            self.task_time_cache = {}
            self.task_time_cache_hash = self.sessions_hash
            
        # 检查缓存是否仍然有效
        if self.task_time_cache_hash != self.sessions_hash:
            # 如果会话数据已更改，则清除缓存
            self.task_time_cache = {}
            self.task_time_cache_hash = self.sessions_hash
            
        # 尝试从缓存获取
        if task_id in self.task_time_cache:
            return self.task_time_cache[task_id]
            
        # 计算总时间
        total_seconds = 0
        for session in self.focus_sessions:
            if session.task_id == task_id and session.end_time and not session.abandoned:
                total_seconds += session.duration
                
        # 存入缓存
        self.task_time_cache[task_id] = total_seconds
        return total_seconds

    def save_sessions(self):
        # 生成当前会话数据的哈希值
        sessions_data = [session.to_dict() for session in self.focus_sessions]
        current_hash = hash(json.dumps(sessions_data, sort_keys=True))
        
        # 只有当哈希值不同时（数据有变化）才写入文件
        if current_hash != self.sessions_hash:
            with open(self.sessions_file, "w", encoding="utf-8") as f:
                json.dump(sessions_data, f, ensure_ascii=False, indent=2)
            self.sessions_hash = current_hash

    def load_sessions(self):
        if os.path.exists(self.sessions_file):
            try:
                with open(self.sessions_file, "r", encoding="utf-8") as f:
                    sessions_data = json.load(f)
                    self.focus_sessions = [FocusSession.from_dict(session_data) for session_data in sessions_data]
                    # 初始化哈希值
                    self.sessions_hash = hash(json.dumps(sessions_data, sort_keys=True))
            except json.JSONDecodeError:
                self.focus_sessions = []
                self.sessions_hash = hash("[]")

    def get_tasks(self):
        return self.tasks

    def get_task_by_id(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def complete_task(self, task_id, summary=None):
        task = self.get_task_by_id(task_id)
        if task:
            task.status = "已完成"
            task.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            task.summary = summary
            self.save_tasks()
            # 更新任务索引
            search_index.update_task(task)
            # 清除任务视图缓存，确保下次请求时重新加载
            if hasattr(self, 'task_view_cache'):
                self.task_view_cache = {}
            return True
        return False

    def uncomplete_task(self, task_id):
        task = self.get_task_by_id(task_id)
        if task:
            task.status = "未完成"
            task.completed_at = None
            self.save_tasks()
            # 更新任务索引
            search_index.update_task(task)
            # 清除任务视图缓存，确保下次请求时重新加载
            if hasattr(self, 'task_view_cache'):
                self.task_view_cache = {}
            return True
        return False

    def delete_task(self, task_id):
        task = self.get_task_by_id(task_id)
        if task:
            # Remove task from index before deleting
            search_index.remove_task(task)
            self.tasks.remove(task)
            self.save_tasks()
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

    def update_task(self, task):
        """更新任务索引，确保完全重建索引条目"""
        # 首先尝试找到任务在列表中的当前位置
        try:
            task_idx = next(i for i, t in enumerate(self.tasks) if t.id == task.id)
            # 获取旧的任务对象，用于从索引中移除旧的数据
            old_task = self.tasks[task_idx]
            
            # 从索引中完全移除旧的数据
            # 先从状态索引中移除
            old_status = old_task.status.lower()
            if task_idx in self.status_index[old_status]:
                self.status_index[old_status].remove(task_idx)
            
            # 从标题索引中移除
            for word in re.findall(r'\w+', old_task.title.lower()):
                if word in self.title_index and task_idx in self.title_index[word]:
                    self.title_index[word].remove(task_idx)
            
            # 从描述索引中移除
            if old_task.description:
                for word in re.findall(r'\w+', old_task.description.lower()):
                    if word in self.description_index and task_idx in self.description_index[word]:
                        self.description_index[word].remove(task_idx)
            
            # 从优先级索引中移除
            old_priority = old_task.priority.lower()
            if task_idx in self.priority_index[old_priority]:
                self.priority_index[old_priority].remove(task_idx)
            
            # 从标签索引中移除
            for tag in old_task.tags:
                tag_key = tag.lower()
                if tag_key in self.tag_index and task_idx in self.tag_index[tag_key]:
                    self.tag_index[tag_key].remove(task_idx)
            
            # 更新任务列表中的任务对象
            self.tasks[task_idx] = task
            
            # 重新添加新的索引条目
            # 索引标题
            for word in re.findall(r'\w+', task.title.lower()):
                self.title_index[word].append(task_idx)
            
            # 索引描述
            if task.description:
                for word in re.findall(r'\w+', task.description.lower()):
                    self.description_index[word].append(task_idx)
            
            # 索引优先级
            self.priority_index[task.priority.lower()].append(task_idx)
            
            # 索引状态
            self.status_index[task.status.lower()].append(task_idx)
            
            # 索引标签
            for tag in task.tags:
                self.tag_index[tag.lower()].append(task_idx)
                
        except StopIteration:
            # 如果任务不在列表中，则直接添加它
            self.add_task(task)

    def remove_task(self, task):
        """从索引中删除指定任务"""
        # 找到任务在tasks列表中的索引
        try:
            task_idx = next(i for i, t in enumerate(self.tasks) if t.id == task.id)
        except StopIteration:
            # 如果任务不在索引中，则不需要做任何操作
            return
            
        # 从tasks列表中删除该任务
        self.tasks.pop(task_idx)
        
        # 从各个索引中删除该任务的引用
        # 处理标题索引
        for word in re.findall(r'\w+', task.title.lower()):
            if word in self.title_index and task_idx in self.title_index[word]:
                self.title_index[word].remove(task_idx)
                # 更新所有大于task_idx的索引值，因为我们删除了一项
                self.title_index[word] = [i if i < task_idx else i-1 for i in self.title_index[word]]
        
        # 处理描述索引
        if task.description:
            for word in re.findall(r'\w+', task.description.lower()):
                if word in self.description_index and task_idx in self.description_index[word]:
                    self.description_index[word].remove(task_idx)
                    self.description_index[word] = [i if i < task_idx else i-1 for i in self.description_index[word]]
        
        # 处理优先级索引
        priority_key = task.priority.lower()
        if priority_key in self.priority_index and task_idx in self.priority_index[priority_key]:
            self.priority_index[priority_key].remove(task_idx)
            self.priority_index[priority_key] = [i if i < task_idx else i-1 for i in self.priority_index[priority_key]]
        
        # 处理状态索引
        status_key = task.status.lower()
        if status_key in self.status_index and task_idx in self.status_index[status_key]:
            self.status_index[status_key].remove(task_idx)
            self.status_index[status_key] = [i if i < task_idx else i-1 for i in self.status_index[status_key]]
        
        # 处理标签索引
        for tag in task.tags:
            tag_key = tag.lower()
            if tag_key in self.tag_index and task_idx in self.tag_index[tag_key]:
                self.tag_index[tag_key].remove(task_idx)
                self.tag_index[tag_key] = [i if i < task_idx else i-1 for i in self.tag_index[tag_key]]

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
        if status is not None:  # 只有当status不是None时才过滤状态
            status_key = status.lower()
            # 检查是否有该状态的索引
            if status_key in self.status_index:
                status_matches = set(self.status_index[status_key])
                result_set &= status_matches
            else:
                # 如果索引中没有匹配的状态，返回空列表
                return []
        # 注意: 如果状态过滤为None，则保留所有结果
            
        # Apply tag filter
        if tag:
            tag_matches = set(self.tag_index.get(tag.lower(), set()))
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
    # 每次访问主页都重新初始化搜索索引，确保任务状态正确
    initialize_index()
    
    tasks = manager.get_tasks()
    
    # 获取查询参数
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'created_at')  # 默认按创建时间排序
    sort_order = request.args.get('sort_order', 'desc')  # 默认降序
    
    # 处理状态过滤参数 - 如果status参数不存在于请求中，默认为"未完成"；如果存在但为空，表示查看所有状态
    if 'status' in request.args:
        filter_status = request.args.get('status')
        if filter_status == '':
            filter_status = None  # None 表示不进行状态过滤
    else:
        filter_status = '未完成'  # 默认只显示未完成任务
        
    filter_tag = request.args.get('tag', '')  # 默认不过滤标签
    priority_filter = request.args.get('priority', '')  # 默认不按优先级过滤
    
    # 构建缓存键
    cache_key = f"{sort_by}_{sort_order}_{filter_status}_{filter_tag}_{priority_filter}_{search_query}"
    
    # 使用cached_property模式：保存最近的查询结果
    if not hasattr(manager, 'task_view_cache'):
        manager.task_view_cache = {}
    
    # 检查缓存是否有效
    last_modified = getattr(manager, 'tasks_last_modified', None)
    current_modified = manager.tasks_hash
    if last_modified != current_modified:
        # 清除缓存
        manager.task_view_cache = {}
        manager.tasks_last_modified = current_modified
        
    # 从缓存获取结果或重新计算
    if cache_key in manager.task_view_cache:
        tasks_data = manager.task_view_cache[cache_key]
        all_tags = manager.all_tags_cache if hasattr(manager, 'all_tags_cache') else set()
    else:
        # 使用搜索索引进行过滤
        filtered_tasks = search_index.search(
            query=search_query,
            priority=priority_filter,
            status=filter_status,
            tag=filter_tag
        )
        
        # 排序任务
        if sort_by == 'created_at':
            filtered_tasks.sort(key=lambda x: x.created_at, reverse=(sort_order == 'desc'))
        elif sort_by == 'priority':
            priority_order = {"高": 0, "中": 1, "低": 2}
            filtered_tasks.sort(key=lambda x: priority_order.get(x.priority, 3), reverse=(sort_order == 'desc'))
        elif sort_by == 'status':
            filtered_tasks.sort(key=lambda x: x.status, reverse=(sort_order == 'desc'))
        elif sort_by == 'expected_time':
            # 按预期时间排序，None值排在最后
            filtered_tasks.sort(key=lambda x: (x.expected_time is None, x.expected_time or 0), reverse=(sort_order == 'desc'))
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
        
        # 保存到缓存
        manager.task_view_cache[cache_key] = tasks_data
        manager.all_tags_cache = all_tags
    
    # 将None值转换回空字符串用于前端显示
    display_status = filter_status if filter_status is not None else ""
    
    return render_template('index.html', 
                          tasks=tasks_data, 
                          all_tags=sorted(all_tags), 
                          search_query=search_query,
                          priority_filter=priority_filter, 
                          status_filter=display_status, 
                          tag_filter=filter_tag,
                          sort_by=sort_by,
                          sort_order=sort_order)

@app.route('/add_task', methods=['POST'])
def add_task():
    title = request.form.get('title')
    description = request.form.get('description', '')
    priority = request.form.get('priority', '中')
    expected_time_str = request.form.get('expected_time', '')
    
    try:
        expected_time = int(expected_time_str) if expected_time_str else None
    except ValueError:
        expected_time = None
    
    # 处理标签（Select2多选）
    tags = request.form.getlist('tags')
    
    if title:
        task = manager.add_task(title, description, priority, expected_time, tags)
        # Add task to search index
        search_index.add_task(task)
        return redirect('/')
    return redirect('/')

@app.route('/complete_task/<task_id>', methods=['GET', 'POST'])
def complete_task(task_id):
    if request.method == 'POST':
        summary = request.form.get('summary', '')
        success = manager.complete_task(task_id, summary)
    else:
        # 如果是GET请求，显示任务完成表单
        task = manager.get_task_by_id(task_id)
        if task:
            return render_template('complete_task.html', task=task)
        return redirect('/')
    
    # 重新初始化搜索索引确保数据一致性
    if success:
        initialize_index()
    
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
    success = manager.uncomplete_task(task_id)
    
    # 重新初始化搜索索引确保数据一致性
    if success:
        initialize_index()
    
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
    success = manager.delete_task(task_id)
    
    # 重新初始化搜索索引确保数据一致性
    if success:
        initialize_index()
    
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
    # 重新初始化索引确保数据一致性
    initialize_index()
    
    # Get search parameters
    search_query = request.args.get('search', '')
    priority_filter = request.args.get('priority', '')
    
    # 处理状态过滤参数 - 如果status参数不存在于请求中，表示查看所有状态
    if 'status' in request.args:
        status_filter = request.args.get('status')
    else:
        status_filter = None  # None 表示不进行状态过滤
        
    tag_filter = request.args.get('tag', '')
    
    # 获取排序参数
    sort_by = request.args.get('sort_by', 'created_at')  # 默认按创建时间排序
    sort_order = request.args.get('sort_order', 'desc')  # 默认降序
    
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
    
    # 排序任务
    if sort_by == 'created_at':
        tasks_data.sort(key=lambda x: x['created_at'], reverse=(sort_order == 'desc'))
    elif sort_by == 'priority':
        priority_order = {"高": 0, "中": 1, "低": 2}
        tasks_data.sort(key=lambda x: priority_order.get(x['priority'], 3), reverse=(sort_order == 'desc'))
    elif sort_by == 'expected_time':
        # 对预期时间排序，None值排在最后
        tasks_data.sort(key=lambda x: (x['expected_time'] is None, x['expected_time'] or 0), reverse=(sort_order == 'desc'))
    elif sort_by == 'total_time':
        tasks_data.sort(key=lambda x: x['total_time'], reverse=(sort_order == 'desc'))
    
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
    date_str = request.args.get('date')
    if not date_str:  # 如果日期参数为空，使用当天日期
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 使用缓存减少重复计算
    if not hasattr(manager, 'focus_history_cache'):
        manager.focus_history_cache = {}
    
    # 检查缓存是否有效
    sessions_last_modified = getattr(manager, 'sessions_last_modified', None)
    current_modified = manager.sessions_hash
    if sessions_last_modified != current_modified:
        # 清除缓存
        manager.focus_history_cache = {}
        manager.sessions_last_modified = current_modified
    
    # 尝试从缓存获取结果
    if date_str in manager.focus_history_cache:
        cache_data = manager.focus_history_cache[date_str]
        return render_template('focus_history.html', 
                             date=date_str,
                             tasks=cache_data['tasks_data'], 
                             total_focus_time_str=cache_data['total_focus_time_str'],
                             total_tasks=cache_data['total_tasks'], 
                             completed_tasks=cache_data['completed_tasks'],
                             chart_data=json.dumps(cache_data['chart_data']),
                             timeline_data=json.dumps(cache_data['timeline_data']))
    
    # 获取该日期的所有专注会话
    sessions = manager.get_sessions_by_date(date_str)
    
    # 预先解析日期字符串，避免重复解析
    if not date_str:
        # 如果日期为空，使用当天日期
        date_str = datetime.now().strftime("%Y-%m-%d")
        date_obj = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            # 如果日期格式无效，使用当天日期
            date_str = datetime.now().strftime("%Y-%m-%d")
            date_obj = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 按任务ID分组并计算每个任务的专注时间
    task_times = {}
    task_sessions = {}
    task_colors = {}
    
    # 创建一个基于任务总数的预定义颜色列表
    def generate_distinct_colors(num_tasks):
        """生成足够多的不同颜色，使用均匀分布的HSL色调"""
        colors = []
        for i in range(num_tasks):
            # 计算均匀分布的色调值，确保最大色调差异
            hue = int(i * (360 / max(1, num_tasks))) % 360
            # 随机调整饱和度和亮度，保持颜色鲜艳
            saturation = 70 + (hash(str(i)) % 20)
            lightness = 40 + (hash(str(i + 100)) % 20)
            colors.append(f"hsl({hue}, {saturation}%, {lightness}%)")
        return colors
    
    # 先获取任务ID列表
    distinct_task_ids = []
    for session in sessions:
        if session.end_time and not session.abandoned:
            task_id = session.task_id
            if task_id not in distinct_task_ids:
                distinct_task_ids.append(task_id)
    
    # 为每个任务生成唯一颜色
    distinct_colors = generate_distinct_colors(len(distinct_task_ids))
    task_color_map = {task_id: distinct_colors[i] for i, task_id in enumerate(distinct_task_ids)}
    
    for session in sessions:
        if session.end_time and not session.abandoned:  # 只统计已结束且未放弃的会话
            task_id = session.task_id
            if task_id not in task_times:
                task_times[task_id] = 0
                task_sessions[task_id] = []
                # 使用预先生成的唯一颜色
                task_colors[task_id] = task_color_map.get(task_id, f"hsl({hash(task_id) % 360}, 70%, 50%)")  # 后面的是备用方案
            
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
            task_data['color'] = task_colors[task_id]
            
            # 添加会话详情
            for session in task_sessions[task_id]:
                start_time_str = session.start_time.strftime("%H:%M:%S")
                end_time_str = session.end_time.strftime("%H:%M:%S") if session.end_time else ""
                
                session_data = {
                    'id': session.id,
                    'start_time': start_time_str,
                    'end_time': end_time_str,
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
    total_focus_time_str = Task.format_time(total_focus_time) if tasks_data else "00:00:00"
    
    # 准备图表数据 - 使用已经缓存的颜色
    chart_data = []
    for task in tasks_data:
        chart_data.append({
            'task': task['title'],  # 确保使用task作为属性名
            'time': task['focus_time'],
            'color': task['color']
        })
    
    # 准备时间轴数据 - 预计算并一次性转换日期
    timeline_data = []
    
    for task in tasks_data:
        for session in task['sessions']:
            if session['start_time'] and session['end_time']:
                try:
                    # 组合日期和时间，避免重复字符串拼接
                    start = datetime.combine(date_obj.date(), 
                                           datetime.strptime(session['start_time'], "%H:%M:%S").time())
                    end = datetime.combine(date_obj.date(),
                                         datetime.strptime(session['end_time'], "%H:%M:%S").time())
                    
                    # 处理跨日的情况
                    if end < start:
                        end = end + timedelta(days=1)
                    
                    timeline_data.append({
                        'task_id': task['id'],
                        'task_title': task['title'],
                        'start': start.strftime("%Y-%m-%d %H:%M:%S"),
                        'end': end.strftime("%Y-%m-%d %H:%M:%S"),
                        'duration': session['duration'],
                        'color': task['color']  # 使用已缓存的颜色
                    })
                except (ValueError, TypeError) as e:
                    app.logger.error(f"Error processing session: {e}")
                    # 跳过有问题的会话
                    continue
    
    # 保存到缓存
    manager.focus_history_cache[date_str] = {
        'tasks_data': tasks_data,
        'total_focus_time_str': total_focus_time_str,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'chart_data': chart_data,
        'timeline_data': timeline_data
    }
    
    # 确保数据是可序列化的
    chart_data_json = json.dumps(chart_data)
    timeline_data_json = json.dumps(timeline_data)
    
    return render_template('focus_history.html', 
                          date=date_str,
                          tasks=tasks_data,
                          total_focus_time_str=total_focus_time_str,
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
        date_str = request.args.get('date', '')
        
        # 即使日期为空，也进行正常重定向
        # focus_history路由会处理空日期的情况
        return jsonify({'success': True, 'redirect': f'/focus_history?date={date_str}'})
    return jsonify({'success': False, 'error': '找不到指定的专注会话'}), 404

@app.route('/view_summary/<task_id>')
def view_summary(task_id):
    task = manager.get_task_by_id(task_id)
    if task and task.status == "已完成":
        return render_template('view_summary.html', task=task)
    else:
        flash('任务不存在或尚未完成！', 'warning')
        return redirect(url_for('index'))

@app.route('/edit_summary/<task_id>', methods=['GET', 'POST'])
def edit_summary(task_id):
    task = manager.get_task_by_id(task_id)
    if not task:
        flash('任务不存在！', 'warning')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        summary = request.form.get('summary', '')
        task.summary = summary
        manager.save_tasks()
        search_index.update_task(task)
        flash('总结已更新！', 'success')
        return redirect(url_for('view_summary', task_id=task.id))
    
    return render_template('edit_summary.html', task=task)

@app.route('/timeline')
def timeline():
    # 获取日期参数，默认为今天
    date_str = request.args.get('date')
    if not date_str:  # 如果日期参数为空，使用当天日期
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 获取客户端时间戳参数
    client_timestamp = request.args.get('timestamp')
    
    # 生成当前时间戳
    timestamp = int(time.time())
    
    # 如果是AJAX请求检查更新（带有时间戳参数）
    if client_timestamp:
        # 检查focus_sessions.json文件的修改时间
        try:
            file_mtime = os.path.getmtime(SESSIONS_FILE)
            # 如果文件修改时间晚于客户端时间戳，需要返回新数据
            if int(file_mtime) > int(client_timestamp):
                # 强制重新加载会话数据
                manager.load_sessions()
        except (OSError, ValueError) as e:
            app.logger.error(f"Error checking file modification time: {e}")
    
    # 总是获取最新的会话数据，不使用缓存
    # 获取所有专注会话，而不仅仅是指定日期的会话
    sessions = manager.focus_sessions
    
    # 预先解析日期字符串，避免重复解析
    if not date_str:
        # 如果日期为空，使用当天日期
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    # 按任务ID分组并计算每个任务的专注时间
    task_times = {}
    task_sessions = {}
    task_colors = {}
    
    # 创建一个基于任务总数的预定义颜色列表
    def generate_distinct_colors(num_tasks):
        """生成足够多的不同颜色，使用均匀分布的HSL色调"""
        colors = []
        for i in range(num_tasks):
            # 计算均匀分布的色调值，确保最大色调差异
            hue = int(i * (360 / max(1, num_tasks))) % 360
            # 随机调整饱和度和亮度，保持颜色鲜艳
            saturation = 70 + (hash(str(i)) % 20)
            lightness = 40 + (hash(str(i + 100)) % 20)
            colors.append(f"hsl({hue}, {saturation}%, {lightness}%)")
        return colors
    
    # 先获取任务ID列表
    distinct_task_ids = []
    for session in sessions:
        if session.end_time and not session.abandoned:
            task_id = session.task_id
            if task_id not in distinct_task_ids:
                distinct_task_ids.append(task_id)
    
    # 为每个任务生成唯一颜色
    distinct_colors = generate_distinct_colors(len(distinct_task_ids))
    task_color_map = {task_id: distinct_colors[i] for i, task_id in enumerate(distinct_task_ids)}
    
    for session in sessions:
        if session.end_time and not session.abandoned:  # 只统计已结束且未放弃的会话
            task_id = session.task_id
            if task_id not in task_times:
                task_times[task_id] = 0
                task_sessions[task_id] = []
                # 使用预先生成的唯一颜色
                task_colors[task_id] = task_color_map.get(task_id, f"hsl({hash(task_id) % 360}, 70%, 50%)")  # 后面的是备用方案
            
            task_times[task_id] += session.duration
            task_sessions[task_id].append(session)
    
    # 获取任务详情
    tasks_data = []
    
    for task_id, time_spent in task_times.items():
        task = manager.get_task_by_id(task_id)
        if task:
            task_data = task.to_dict()
            task_data['focus_time'] = time_spent
            task_data['focus_time_str'] = task.format_time(time_spent)
            task_data['sessions'] = []
            task_data['color'] = task_colors[task_id]
            
            # 添加会话详情
            for session in task_sessions[task_id]:
                # 格式化日期和时间
                start_date_str = session.start_time.strftime("%Y-%m-%d")
                start_time_str = session.start_time.strftime("%H:%M:%S")
                
                end_date_str = ""
                end_time_str = ""
                if session.end_time:
                    end_date_str = session.end_time.strftime("%Y-%m-%d")
                    end_time_str = session.end_time.strftime("%H:%M:%S")
                
                session_data = {
                    'id': session.id,
                    'start_date': start_date_str,
                    'start_time': start_time_str,
                    'end_date': end_date_str,
                    'end_time': end_time_str,
                    'duration': session.duration,
                    'duration_str': task.format_time(session.duration)
                }
                task_data['sessions'].append(session_data)
            
            tasks_data.append(task_data)
    
    # 准备时间轴数据
    timeline_data = []
    
    for task in tasks_data:
        for session in task['sessions']:
            if session['start_time'] and session['end_time']:
                try:
                    # 使用完整日期和时间
                    start = datetime.strptime(
                        f"{session['start_date']} {session['start_time']}",
                        "%Y-%m-%d %H:%M:%S"
                    )
                    
                    end = datetime.strptime(
                        f"{session['end_date']} {session['end_time']}",
                        "%Y-%m-%d %H:%M:%S"
                    )
                    
                    # 处理跨日的情况
                    if end < start:
                        end = end + timedelta(days=1)
                    
                    timeline_data.append({
                        'task_id': task['id'],
                        'task_title': task['title'],
                        'start': start.strftime("%Y-%m-%d %H:%M:%S"),
                        'end': end.strftime("%Y-%m-%d %H:%M:%S"),
                        'duration': session['duration'],
                        'color': task['color'],
                        'date': session['start_date']  # 添加日期信息方便前端筛选
                    })
                except (ValueError, TypeError) as e:
                    app.logger.error(f"Error processing session: {e}")
                    # 跳过有问题的会话
                    continue
    
    # 添加时间戳到时间轴数据中，方便前端检测更新
    timestamp = int(time.time())
    
    return render_template('timeline.html', 
                          date=date_str,
                          timestamp=timestamp,
                          timeline_data=json.dumps(timeline_data))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=12345, debug=True)