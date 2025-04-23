import os
import streamlit as st
import pandas as pd
import boto3
import json
import time
from typing import List, Dict, Any, Optional

# Initialize Boto3 client
connect_client = boto3.client("connect")


def get_selected_queues(queues: pd.DataFrame) -> List[str]:
    """
    Retrieve a list of selected queue ARNs from the provided queues DataFrame.

    Args:
        queues (pd.DataFrame): DataFrame containing queue information.

    Returns:
        list: List of selected queue ARNs.
    """
    if queues.empty:
        return []
    return queues['Arn'].tolist()  # More efficient than iterrows


def load_configuration(connect_instance_id: str) -> bool:
    """
    Load the Connect instance configuration and related data.

    Args:
        connect_instance_id (str): Connect instance ID.

    Returns:
        bool: True if the configuration was loaded successfully, False otherwise.
    """
    try:
        res = connect_client.describe_instance(InstanceId=connect_instance_id)
        connect_filtered = {k: v for k, v in res['Instance'].items() if k in ['Id', 'Arn']}
        with open('connect.json', 'w') as f:
            json.dump(connect_filtered, f)

        # Load queues
        res = connect_client.list_queues(InstanceId=connect_instance_id, QueueTypes=['STANDARD'])
        df = pd.DataFrame(res['QueueSummaryList'])
        if len(df) > 0:
            df.to_csv("queues.csv", index=False)

        # Load users
        res = connect_client.list_users(InstanceId=connect_instance_id)
        df = pd.DataFrame(res['UserSummaryList'])
        if len(df) > 0:
            df.to_csv("users.csv", index=False)

        # Load agent statuses
        load_agent_statuses(connect_instance_id)

        st.success("Configuration loaded!")
        return True
    except Exception as e:
        st.error(f'Load Configuration Failed: {str(e)}')
        return False


def load_agent_statuses(connect_instance_id: str) -> None:
    """
    Load available agent statuses and save to file.
    
    Args:
        connect_instance_id (str): Connect instance ID.
    """
    try:
        response = connect_client.list_agent_statuses(
            InstanceId=connect_instance_id,
            MaxResults=100  # Adjust based on your needs
        )
        
        status_list = response.get('AgentStatusSummaryList', [])
        
        # Process paginated results if necessary
        while 'NextToken' in response:
            response = connect_client.list_agent_statuses(
                InstanceId=connect_instance_id,
                MaxResults=100,
                NextToken=response['NextToken']
            )
            status_list.extend(response.get('AgentStatusSummaryList', []))
        
        # Convert to DataFrame and save
        df = pd.DataFrame(status_list)
        if not df.empty:
            df.to_csv("agent_statuses.csv", index=False)
            st.session_state.agent_statuses = df
            return df
        else:
            st.warning("No agent statuses found")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading agent statuses: {str(e)}")
        return pd.DataFrame()


def get_available_statuses() -> List[Dict[str, str]]:
    """
    Get list of available statuses with ID and Name.
    
    Returns:
        List of dictionaries with status ID and name
    """
    if os.path.exists("agent_statuses.csv"):
        try:
            statuses_df = pd.read_csv("agent_statuses.csv")
            if not statuses_df.empty:
                status_list = []
                for _, row in statuses_df.iterrows():
                    status_list.append({
                        'id': row['Id'],
                        'name': row['Name'],
                        'type': row.get('Type', 'CUSTOM')  # Default to CUSTOM if Type is not in columns
                    })
                return status_list
            else:
                return []
        except Exception:
            return []
    return []


def load_user_data(connect_instance_id: str, queues_selected: pd.DataFrame) -> pd.DataFrame:
    """
    Load user data for the selected queues.

    Args:
        connect_instance_id (str): Connect instance ID.
        queues_selected (pd.DataFrame): DataFrame containing selected queues.

    Returns:
        pd.DataFrame: DataFrame containing user data.
    """
    try:
        res = connect_client.get_current_user_data(
            InstanceId=connect_instance_id,
            Filters={'Queues': get_selected_queues(queues_selected)}
        )

        df = pd.read_csv("users.csv")

        user_data = []
        for user in res['UserDataList']:
            user_id = user['User']['Id']
            user_name = df.loc[df['Id'] == user_id, 'Username'].values[0]
            status_name = user['Status']['StatusName']
            status_id = user['Status'].get('StatusId', '')  # Add status ID
            routing_profile_id = user['RoutingProfile']['Id']
            user_data.append({
                'UserId': user_id,
                'UserName': user_name,
                'StatusName': status_name,
                'StatusId': status_id,
                'RoutingProfileId': routing_profile_id
            })

        # 将用户数据保存到session state
        result_df = pd.DataFrame(user_data)
        st.session_state.user_data = result_df
        return result_df
    except Exception as e:
        st.error(f'加载用户数据失败: {str(e)}')
        return pd.DataFrame()


def validate_queue_selection(queues_selected: Optional[pd.DataFrame]) -> bool:
    """
    验证是否已选择Queue
    
    Args:
        queues_selected (pd.DataFrame): 选择的Queue数据
        
    Returns:
        bool: 是否通过验证
    """
    if queues_selected is None or queues_selected.empty:
        st.warning('请至少选择一个Queue后再加载用户数据')
        return False
    return True


def update_agent_status(connect_instance_id: str, agent_id: str, status_id: str) -> bool:
    """
    Updates an agent's status in Amazon Connect
    
    Args:
        connect_instance_id (str): Connect instance ID
        agent_id (str): Agent/User ID
        status_id (str): Status ID to set
        
    Returns:
        bool: Success status of the operation
    """
    try:
        connect_client.put_user_status(
            InstanceId=connect_instance_id,
            UserId=agent_id,
            AgentStatusId=status_id
        )
        return True
    except Exception as e:
        st.error(f"更新状态失败: {str(e)}")
        return False


def display_user_data(user_data: pd.DataFrame, connect_instance_id: str) -> None:
    """
    显示用户数据并处理状态更新
    
    Args:
        user_data (pd.DataFrame): 用户数据DataFrame
        connect_instance_id (str): Connect instance ID
    """
    # 加载可用状态
    available_statuses = get_available_statuses()
    status_names = [status['name'] for status in available_statuses]
    status_mapping = {status['name']: status['id'] for status in available_statuses}
    
    # 创建表头
    header_col1, header_col2, header_col3, header_col4, header_col5 = st.columns([2, 2, 3, 2, 1])
    with header_col1:
        st.markdown("**用户名**")
    with header_col2:
        st.markdown("**当前状态**")
    with header_col3:
        st.markdown("**新状态**")
    with header_col4:
        st.markdown("**路由配置文件**")
    with header_col5:
        st.markdown("**操作**")
    
    # 为每行创建一个唯一的key
    for index, row in user_data.iterrows():
        col1, col2, col3, col4, col5 = st.columns([2, 2, 3, 2, 1])
        
        with col1:
            st.text(row['UserName'])
        
        with col2:
            st.text(row['StatusName'])
            
        with col3:
            # 使用selectbox显示状态，并存储在session state中
            key = f"new_status_{row['UserId']}"
            if key not in st.session_state:
                # 尝试找到当前状态在列表中的索引，如果不存在则默认为0
                try:
                    default_index = status_names.index(row['StatusName']) if row['StatusName'] in status_names else 0
                except ValueError:
                    default_index = 0
                st.session_state[key] = status_names[default_index] if status_names else "No Status Available"
            
            if status_names:
                new_status = st.selectbox(
                    label="New Status",
                    options=status_names,
                    key=key,
                    label_visibility='collapsed'
                )
            else:
                st.text("No status options available")
                new_status = None
        
        with col4:
            # 显示路由配置文件
            st.text(row['RoutingProfileId'])
            
        with col5:
            # 添加更新按钮
            if st.button("更新", key=f"update_{row['UserId']}") and new_status:
                if new_status != row['StatusName']:
                    status_id = status_mapping.get(new_status)
                    if status_id:
                        with st.spinner(f"正在更新 {row['UserName']} 的状态..."):
                            success = update_agent_status(connect_instance_id, row['UserId'], status_id)
                            if success:
                                st.success(f"已更新 {row['UserName']} 的状态为 {new_status}")
                                # 刷新用户数据以显示新状态
                                time.sleep(1)  # 短暂延迟确保API状态已更新
                                st.rerun()
                    else:
                        st.error(f"找不到状态 '{new_status}' 的ID")
                else:
                    st.info("状态未变更")


def main():
    st.set_page_config(page_title="Amazon Connect Contact User Management Tool", layout="wide")

    # App title
    st.header("Amazon Connect Contact User Management Tool")

    connect_instance_id = ''
    queues_selected = None

    if os.path.exists('connect.json'):
        with open('connect.json') as f:
            connect_data = json.load(f)
            connect_instance_id = connect_data['Id']

    # Connect configuration
    connect_instance_id = st.text_input('Connect Instance ID', value=connect_instance_id)

    # Load configuration
    load_button = st.button('Load Configuration')
    if load_button:
        with st.spinner('Loading configuration...'):
            if load_configuration(connect_instance_id):
                st.experimental_rerun()

    # Queue configuration
    if os.path.exists('queues.csv'):
        queues = pd.read_csv("queues.csv")
        queues_name_selected = st.multiselect('Select Queues', queues['Name'].tolist())
        queues_selected = queues[queues['Name'].isin(queues_name_selected)]

    # Load user data
    if os.path.exists('queues.csv'):
        load_user_button = st.button('Load Users')
        if load_user_button:
            if validate_queue_selection(queues_selected):
                user_data = load_user_data(connect_instance_id, queues_selected)
                if not user_data.empty:
                    st.success(f"Loaded {len(user_data)} users")

        # 如果session state中有用户数据，显示它
        if 'user_data' in st.session_state and not st.session_state.user_data.empty:
            display_user_data(st.session_state.user_data, connect_instance_id)


if __name__ == "__main__":
    main()