import os
import streamlit as st
import pandas as pd
import boto3
import json

# Initialize Boto3 client
connect_client = boto3.client("connect")


def get_selected_queues(queues):
    """
    Retrieve a list of selected queue ARNs from the provided queues DataFrame.

    Args:
        queues (pd.DataFrame): DataFrame containing queue information.

    Returns:
        list: List of selected queue ARNs.
    """
    data = [row['Arn'] for index, row in queues.iterrows()]
    return data


def load_configuration(connect_instance_id):
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

        st.success("Configuration loaded!")
        return True
    except Exception as e:
        st.error('Load Configuration Failed')
        return False


def load_user_data(connect_instance_id, queues_selected):
    """
    Load user data for the selected queues.

    Args:
        connect_instance_id (str): Connect instance ID.
        queues_selected (pd.DataFrame): DataFrame containing selected queues.

    Returns:
        pd.DataFrame: DataFrame containing user data.
    """
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
        user_data.append({'UserName': user_name, 'StatusName': status_name})

    return pd.DataFrame(user_data)


def main():
    st.set_page_config(page_title="Amazon Connect Contact Get Current User Tool!", layout="wide")

    # App title
    st.header(f"Amazon Connect Contact Get Current User Tool!")

    # 使用session_state来管理状态
    if 'configuration_loaded' not in st.session_state:
        st.session_state.configuration_loaded = False

    connect_instance_id = ''
    queues_selected = ''

    if os.path.exists('connect.json'):
        with open('connect.json') as f:
            connect_data = json.load(f)
            connect_instance_id = connect_data['Id']

    # Connect configuration
    connect_instance_id = st.text_input('Connect Instance Id', value=connect_instance_id)

    # Load configuration
    load_button = st.button('Load')
    if load_button:
        with st.spinner('Loading...'):
            if load_configuration(connect_instance_id):
                st.session_state.configuration_loaded = True

    # Queue configuration
    if os.path.exists('queues.csv'):
        queues = pd.read_csv("queues.csv")
        queues_name_selected = st.multiselect('Queues', queues['Name'])
        queues_selected = queues[queues['Name'].isin(queues_name_selected)]

    # Load user data
    if os.path.exists('queues.csv'):
        load_user_button = st.button('Load Users')
        if load_user_button:
            user_data = load_user_data(connect_instance_id, queues_selected)
            st.write(user_data)



if __name__ == "__main__":
    main()