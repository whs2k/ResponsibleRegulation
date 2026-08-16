import helper
import pandas as pd
import requests
import argparse
from google import genai
import email_sender
from datetime import datetime, timedelta

def main():
	# Create an ArgumentParser object
	parser = argparse.ArgumentParser(description="A sample program to demonstrate argument parsing")

	# Add named arguments
	parser.add_argument("--regulation_api_key", type=str, help="https://open.gsa.gov/api/regulationsgov/")
	parser.add_argument("--gemini_api_key", type=str, help="https://ai.google.dev/gemini-api/docs/api-key")

	# Parse the arguments
	args = parser.parse_args()

	authenticated_gemini_client = genai.Client(api_key=args.gemini_api_key)
	regulation_api_key = args.regulation_api_key

	url = 'https://api.regulations.gov/v4/documents?filter[agencyId]=EPA&filter[documentType]=Proposed%20Rule&sort=-postedDate&api_key={}'.format(regulation_api_key)
	
	try:
		response_data = requests.get(url).json().get('data', [])
	except Exception as e:
		print("Error fetching from regulations.gov:", e)
		return

	if not response_data:
		print("No data received from API.")
		return

	df_output = helper.create_dataframe_from_list_of_dicts(response_data)
	if df_output.empty:
		print("No valid proposed rules found.")
		return

	df_output['Agency']='EPA'
	df_output['Proposed Rule Link'] = 'https://www.regulations.gov/document/' + df_output.id
	df_output['Proposed Rule Title'] = df_output['attributes.title']
	df_output['Proposed Rule Posted Date'] = pd.to_datetime(df_output['attributes.postedDate'])

	# Filter by rules posted between 10 days ago and 3 days ago
	start_date = datetime.now() - timedelta(days=10)
	end_date = datetime.now() - timedelta(days=3)
	df_recent = df_output[(df_output['Proposed Rule Posted Date'].dt.tz_localize(None) >= start_date) & 
	                      (df_output['Proposed Rule Posted Date'].dt.tz_localize(None) <= end_date)].copy()

	if df_recent.empty:
		print("No new rules posted in the target date range.")
		return

	df_recent['Proposed Rule Posted Date'] = df_recent['Proposed Rule Posted Date'].astype(str)
	df_mini = df_recent.head(3).copy()

	df_mini['AI Generated Comment'] = df_mini['id'].apply(lambda x: helper.generate_comment(
	    proposed_rule_id_=x, gemini_client=authenticated_gemini_client, 
	    regulation_api_key_=regulation_api_key, sleep_seconds=15, gemini_model='gemini-3.6-flash'))

	df_xport = df_mini[['Agency','Proposed Rule Title',
	                    'Proposed Rule Link','Proposed Rule Posted Date',
	                    'AI Generated Comment']]
	html_string = helper.dataframe_to_mdb_html(df_xport)

	with open("index.html", "w") as f:
	    f.write(html_string)

	# Send email
	email_sender.send_regulation_email(df_xport)

if __name__ == "__main__":
	main()
