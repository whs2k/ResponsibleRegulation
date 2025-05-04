from google import genai
import requests 
import pandas as pd
import time
from datetime import datetime
import requests
import os


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

def generate_comment(proposed_rule_id_,  gemini_client, regulation_api_key_, gemini_prompt='NA', sleep_seconds=0, print_prompt=False):
    proposed_rule_id = proposed_rule_id_
    proposed_rule_url = 'https://api.regulations.gov/v4/documents/{}?api_key={}'.format(proposed_rule_id,regulation_api_key_)
    proposed_rule_file_url = requests.get(proposed_rule_url).json()['data']['attributes']['fileFormats'][1]['fileUrl']
    proposed_rule_file_title = requests.get(proposed_rule_url).json()['data']['attributes']['title']
    proposed_rule_file_name = proposed_rule_file_title+'.htm'
    print(proposed_rule_file_name)
    #proposed_rule_text = BeautifulSoup(requests.get(proposed_rule_file_url).content, "html.parser").get_text()
    with open(proposed_rule_file_name, "wb") as f:
                # Write the content of the response to the file
                f.write(requests.get(proposed_rule_file_url).content)
    
    #print(proposed_rule_file_url)
    print(proposed_rule_file_name)
    print('https://www.regulations.gov/document/{}'.format(proposed_rule_id))

    epa_proposed_rule_htm = gemini_client.files.upload(file=proposed_rule_file_name)
    if gemini_prompt == 'NA':
        
        
        gemini_prompt_final = ['''Hi Gemini! I'm an an environmental researcher trying to understand the affect of the following proposed EPA regulation.
        Can you review it and: (1) summarize the proposed rule, (2) identify the fundamental reasons and data provided in justification of the propsed rule and (3) provide research and data that might challenge each of the fundamental reasons? 
        For each one of the challenges please include a url link and citation to the peer reviewed paper as a reference?
        
        Here is the document: 
        ''', epa_proposed_rule_htm]
        gemini_prompt_final = ['''Hi Gemini! You are a lawyer and politician working to make the country a better place.
In order to achieve this, you work to make sure that governement regulations are protecting citizens, without undulying penalizing businessese.
Whenever a regulatory agency wants to create a new rule, by law they have to allow the public to comment on the rule, and address the important points.
They then review the significant comments and modify or address them in the final rule. If they don't the courts may strike down the rule when challenged in court.
Comments that are able to provide research and data which challenge the fundamental reasons for that the rule have a better shot at necessitating a change in the rule or reply in th final rule. 

Can you please generate a comment for the proposed rule with the following structure: 
    (1) Introduction and Primary Argument: First cite the specific pages of paragraphs of the rule and the exact text which is challengeable. If it can be replaced with different language then propose what it should be changed to. If the argument invalidates the rule and should block it even from publication then explain so.
    (2) In the next paragraph provide rationale for why the specific sentaces or pargraphs should be changed or removed. Include url links and citations to the peer reviewed papers as a reference. Check that each url link goes to the paper or reference and that it isn't dead.

        Here is the document: 
        ''', epa_proposed_rule_htm]
    else:
        gemini_prompt_final = [gemini_prompt, epa_proposed_rule_htm]
    
    response = gemini_client.models.generate_content(
        model="gemini-1.5-pro",#"gemini-2.0-flash",
        #generation_config={
        #"temperature": 0.8,
        #"max_output_tokens": 2048},
        contents=gemini_prompt_final
    )
    if print_prompt==True:
        print(response.text)
    gemini_client.files.delete(name=epa_proposed_rule_htm.name)
    os.remove(proposed_rule_file_name)
    time.sleep(sleep_seconds)
    return response.text

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
    