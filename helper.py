from google import genai
import requests 
import pandas as pd
import time
from datetime import datetime
import os
from pydantic import BaseModel, Field
from typing import List

class ReferenceItem(BaseModel):
    title: str = Field(description="Title or descriptive citation of the supporting research paper, law review, or report.")
    url: str = Field(description="Direct web URL link to the reference source.")

class Sponsor(BaseModel):
    organization_name: str = Field(description="Name of the company, lobbying firm, or public interest non-profit.")
    email_contacts: List[str] = Field(description="List of possible email contacts for outreach.")
    reason_for_contact: str = Field(description="Strategic reason why this organization should sponsor or support this comment.")

class CommentResponse(BaseModel):
    summary_of_main_idea: str = Field(description="Concise 2-3 sentence overview of what the proposed regulation aims to accomplish.")
    challenges: str = Field(description="Primary legal, scientific, or economic challenges and defects in the proposed rule.")
    references: List[ReferenceItem] = Field(description="List of peer-reviewed articles, case law, or empirical datasets challenging the rule.")
    proposed_comment: str = Field(description="The complete drafted public comment text formatted for submission.")
    sponsors: List[Sponsor] = Field(description="List of 3-5 relevant organizations, firms, or advocacy groups to contact.")


def create_dataframe_from_list_of_dicts(data_list):
    """
    Creates a pandas DataFrame from a list of dictionaries, with nested dictionaries expanded into columns.

    Args:
        data_list (list): A list of dictionaries.

    Returns:
        pandas.DataFrame: A DataFrame with the dictionary keys as columns.
    """

    flattened_data_list = []
    for data_dict in data_list:
        flattened_data = {}
        for key, value in data_dict.items():
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    flattened_data[f"{key}.{nested_key}"] = nested_value
            else:
                flattened_data[key] = value
        flattened_data_list.append(flattened_data)
        
    df = pd.DataFrame(flattened_data_list)
    df = df[~df['attributes.subtype'].isin(['Notice of Proposed Rulemaking (NPRM)','Extension of Comment Period'])].reset_index(drop=True)
    df = df[df['attributes.openForComment']==True].reset_index(drop=True)
    return df

def get_proposed_rule_text_link(proposed_rule_id_, api_key_):
    proposed_rule_url = 'https://api.regulations.gov/v4/documents/{}?api_key={}'.format(proposed_rule_id_,api_key_)
    proposed_rule_file_url = requests.get(proposed_rule_url).json()['data']['attributes']['fileFormats'][1]['fileUrl']
    #proposed_rule_file_title = requests.get(proposed_rule_url).json()['data']['attributes']['title']
    #proposed_rule_file_name = proposed_rule_file_title+'.htm'
    #print(proposed_rule_file_name)
    return proposed_rule_file_url

def generate_comment(proposed_rule_id_,  gemini_client, regulation_api_key_, 
    gemini_prompt='NA', sleep_seconds=0, print_prompt=False, gemini_model='gemini-3.6-flash'):
    proposed_rule_id = proposed_rule_id_
    print('proposed_rule_id: ', proposed_rule_id)
    proposed_rule_url = 'https://api.regulations.gov/v4/documents/{}?api_key={}'.format(proposed_rule_id,regulation_api_key_)
    proposed_rule_files_list = requests.get(proposed_rule_url).json()['data']['attributes']['fileFormats']
    print('proposed_rule_files_list: ',proposed_rule_files_list)
    for rule_file in proposed_rule_files_list:
        if 'htm' in rule_file['format']:
            proposed_rule_file_url = rule_file['fileUrl']
            proposed_rule_file_format = rule_file['format']
            break
    print('proposed_rule_file_url: ', proposed_rule_file_url)
    proposed_rule_file_title = requests.get(proposed_rule_url).json()['data']['attributes']['title']
    proposed_rule_file_name = proposed_rule_file_title + '.' + proposed_rule_file_format 
    print(proposed_rule_file_name)
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    with open(proposed_rule_file_name, "wb") as f:
                f.write(requests.get(proposed_rule_file_url, headers=headers).content)
    
    print(proposed_rule_file_name)
    print('https://www.regulations.gov/document/{}'.format(proposed_rule_id))

    epa_proposed_rule_htm = gemini_client.files.upload(file=proposed_rule_file_name)
    if gemini_prompt == 'NA':
        prompt_text = '''Hi Gemini! You are an expert administrative lawyer and public policy analyst. 
Your goal is to empower civic advocates, researchers, and organizations to engage effectively in the federal rulemaking process.

Please analyze the attached regulatory document and provide a structured JSON response containing:
1. summary_of_main_idea: A clear, objective 2-3 sentence summary of what this proposed regulation aims to do.
2. challenges: The primary legal flaws (e.g. APA procedural defects), scientific/technical weaknesses, or economic issues with the rule's main idea.
3. references: 2-4 peer-reviewed articles, law review publications, or authoritative datasets challenging the rule's main idea, including descriptive titles and direct web URLs.
4. proposed_comment: A formal public comment formatted with specific page/section citations, detailed rationale, and proposed alternative wording.
5. sponsors: 3-5 relevant companies, advocacy groups, or non-profits that would benefit from this comment, including contact emails and strategic outreach reasons.

Here is the document:
'''
        gemini_prompt_final = [
            {"type": "text", "text": prompt_text},
            {"type": "document", "uri": epa_proposed_rule_htm.uri, "mime_type": epa_proposed_rule_htm.mime_type}
        ]
    else:
        gemini_prompt_final = [
            {"type": "text", "text": gemini_prompt},
            {"type": "document", "uri": epa_proposed_rule_htm.uri, "mime_type": epa_proposed_rule_htm.mime_type}
        ]
    
    response = gemini_client.interactions.create(
        model=gemini_model,
        input=gemini_prompt_final,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": CommentResponse.model_json_schema()
        }
    )
    if print_prompt==True:
        print(response.output_text)
    gemini_client.files.delete(name=epa_proposed_rule_htm.name)
    os.remove(proposed_rule_file_name)
    time.sleep(sleep_seconds)
    return response.output_text

def comment_from_ruleid(proposed_rule_id_, regulation_api_key_, gemini_client):
    #get_proposed_rule_text_link = 
    url_ = 'https://api.regulations.gov/v4/documents?filter[agencyId]=EPA&filter[documentType]=Proposed%20Rule&sort=-postedDate&api_key={}'.format(regulation_api_key_)
    
    df_output = create_dataframe_from_list_of_dicts(requests.get(url).json()['data'])

import html

def dataframe_to_mdb_html(df: pd.DataFrame, table_id: str = "df_table") -> str:
    """
    Converts a pandas DataFrame to a complete HTML page string featuring
    a table styled with Material Design Bootstrap (MDB) dark mode.

    Preserves newline characters within DataFrame cells by converting them
    to <br> tags in the HTML output.

    Args:
        df (pd.DataFrame): The pandas DataFrame to convert.
        table_id (str): The HTML ID to assign to the table element.

    Returns:
        str: A string containing the full HTML page source.

    Notes:
        - Requires an internet connection to load MDB CSS and JS from CDN.
        - Uses `escape=False` in `to_html` after manually escaping cell
          content and replacing newlines with <br>. This is necessary
          to render the <br> tags correctly. Be cautious if your DataFrame
          contains untrusted HTML/JavaScript strings, as they might be rendered.
    """
    # --- 1. Preprocess DataFrame ---
    # Create a copy to avoid modifying the original DataFrame
    df_processed = df.copy()

    # Iterate through each cell, escape HTML entities, and replace '\n' with '<br>'
    for col in df_processed.columns:
        df_processed[col] = df_processed[col].apply(
            lambda x: html.escape(str(x)).replace('\n', '<br>') if pd.notna(x) else ''
        )

    # --- 2. Convert DataFrame to HTML Table Fragment ---
    # Define MDB classes for dark theme table styling
    table_classes = [
        "table",
        "table-dark",
        "table-striped",
        "table-bordered",
        "table-hover",
        "align-middle", # Improves vertical alignment for multiline cells
    ]

    # Convert the processed DataFrame to an HTML table string
    # escape=False is crucial here to render our '<br>' tags
    # index=True includes the DataFrame index in the table
    html_table = df_processed.to_html(
        classes=table_classes,
        escape=False, # We already escaped the content manually
        index=True,   # Set to False if you don't want the index
        border=0,     # Border attribute is handled by CSS classes
        table_id=table_id
    )

    # --- 3. Construct Full HTML Page ---
    html_content = f"""
<!DOCTYPE html>
<html lang="en" data-mdb-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DataFrame Viewer</title>
    <link
      href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css"
      rel="stylesheet"
    />
    <link
      href="https://fonts.googleapis.com/css?family=Roboto:300,400,500,700&display=swap"
      rel="stylesheet"
    />
    <link
      href="https://cdnjs.cloudflare.com/ajax/libs/mdb-ui-kit/7.3.2/mdb.min.css"
      rel="stylesheet"
    />
    <style>
        body {{
            padding: 20px; /* Add some padding around the content */
        }}
        .table-container {{
            max-width: 100%;
            overflow-x: auto; /* Add horizontal scroll for wide tables */
        }}
        th, td {{
             white-space: normal !important; /* Ensure text wraps within cells */
             word-wrap: break-word; /* Break long words */
             vertical-align: top; /* Align content to the top for consistency */
        }}
        th {{
            background-color: #343a40; /* Slightly darker header for contrast */
            position: sticky; /* Make table header sticky */
            top: 0; /* Stick to the top */
            z-index: 10; /* Ensure header stays above scrolling content */
        }}
        /* Optional: Style for the index column header */
        thead th:first-child {{
             background-color: #454d55; /* Different background for index header */
        }}
         /* Optional: Style for the index column cells */
        tbody th {{
             background-color: #3e444a;
             position: sticky; /* Make index column sticky */
             left: 0; /* Stick to the left */
             z-index: 5; /* Ensure index stays above row content */
        }}
    </style>
</head>
<body>
    <div class="container-fluid">
        <h1 class="mb-4">Open Proposed Rules and our Generated Comment</h1>
        <div class="table-container shadow-4 rounded-5">
             {html_table}
        </div>
    </div>

    <script
      type="text/javascript"
      src="https://cdnjs.cloudflare.com/ajax/libs/mdb-ui-kit/7.3.2/mdb.umd.min.js"
    ></script>
</body>
</html>
"""
    return html_content

# --- Example Usage ---
if __name__ == "__main__":
    # Create a sample DataFrame with multiline strings
    data = {
        'Column A': ['Row 1, Cell 1', 'Row 2, Cell 1\nLine 2', 'Row 3, Cell 1'],
        'Column B': [10, 20, 30],
        'Column C': ['Description for row 1.', 'Another description\nwith two lines.', 'Final row\nwith\nthree lines.']
    }
    df_example = pd.DataFrame(data)

    # Generate the HTML string
    html_output = dataframe_to_mdb_html(df_example)

    # Save the HTML to a file (optional)
    try:
        with open("dataframe_output.html", "w", encoding="utf-8") as f:
            f.write(html_output)
        print("HTML file 'dataframe_output.html' created successfully.")
        print("Open this file in your web browser to view the table.")
    except Exception as e:
        print(f"Error writing file: {e}")

    # You can also print the HTML string directly (useful for web frameworks)
    # print(html_output)
    