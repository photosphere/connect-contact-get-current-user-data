## About Amazon Connect Contact Get Current User Data Tool
This solution can be used to search contact with specified attributes in Amazon Connect.

### Installation

Clone the repo

```bash
git clone https://github.com/photosphere/connect-contact-get-current-user-data.git
```

cd into the project root folder

```bash
cd connect-contact-get-current-user-data
```

#### Create virtual environment

##### via python

Then you should create a virtual environment named .venv

```bash
python -m venv .venv
```

and activate the environment.

On Linux, or OsX 

```bash
source .venv/bin/activate
```
On Windows

```bash
source.bat
```

Then you should install the local requirements

```bash
pip install -r requirements.txt
```
### Build and run the Application Locally

```bash
streamlit run contact_get_current_user_data.py
```

### Or Build and run the Application on Cloud9

```bash
streamlit run contact_get_current_user_data.py --server.port 8080 --server.address=0.0.0.0 
```

#### Configuration screenshot

