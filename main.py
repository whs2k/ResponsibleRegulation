import helper
import pandas as pd
import requests
import argparse
from google import genai
import email_sender
from datetime import datetime, timedelta
import json
import os

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

	url = 'https://api.regulations.gov/v4/documents?filter[documentType]=Proposed%20Rule&sort=-postedDate&page[size]=250&api_key={}'.format(regulation_api_key)
	
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

	df_output['Agency'] = df_output['attributes.agencyId']
	df_output['Proposed Rule Link'] = 'https://www.regulations.gov/document/' + df_output.id
	df_output['Proposed Rule Title'] = df_output['attributes.title']
	df_output['Proposed Rule Posted Date'] = pd.to_datetime(df_output['attributes.postedDate'])

	# Filter by rules posted in the last 3 days (to account for weekends)
	three_days_ago = datetime.now() - timedelta(days=3)
	df_recent = df_output[df_output['Proposed Rule Posted Date'].dt.tz_localize(None) >= three_days_ago].copy()

	if df_recent.empty:
		print("No new rules posted in the last 3 days.")
		return

	df_recent['Proposed Rule Posted Date'] = df_recent['Proposed Rule Posted Date'].astype(str)

	# Load processed rules history for deduplication
	data_dir = "data"
	history_file = os.path.join(data_dir, "processed_rules.json")
	existing_history = []
	processed_ids = set()

	if os.path.exists(history_file):
		try:
			with open(history_file, "r") as f:
				existing_history = json.load(f)
				processed_ids = {item["id"] for item in existing_history if "id" in item}
		except Exception as e:
			print("Warning: Could not read existing history file:", e)

	# Filter out regulations already processed in previous runs
	df_unprocessed = df_recent[~df_recent['id'].isin(processed_ids)].copy()

	if df_unprocessed.empty:
		print("All recent regulations have already been processed. Skipping Gemini API calls.")
		return

	print(f"Found {len(df_unprocessed)} new unprocessed regulation(s). Processing top 15 max...")
	df_mini = df_unprocessed.head(15).copy()

	df_mini['AI Generated Comment'] = df_mini['id'].apply(lambda x: helper.generate_comment(
	    proposed_rule_id_=x, gemini_client=authenticated_gemini_client, 
	    regulation_api_key_=regulation_api_key, sleep_seconds=15, gemini_model='gemini-3.6-flash'))

	# Save new records into history file
	new_records = []
	for _, row in df_mini.iterrows():
		ai_comment_str = row['AI Generated Comment']
		try:
			ai_data = json.loads(ai_comment_str)
		except Exception:
			ai_data = {"proposed_comment": ai_comment_str, "sponsors": []}

		record = {
			"id": row['id'],
			"agency": row['Agency'],
			"title": row['Proposed Rule Title'],
			"link": row['Proposed Rule Link'],
			"posted_date": row['Proposed Rule Posted Date'],
			"processed_at": datetime.now().isoformat(),
			"ai_data": ai_data
		}
		new_records.append(record)

	# Prepend new records so newest appear first
	updated_history = new_records + existing_history

	os.makedirs(data_dir, exist_ok=True)
	with open(history_file, "w") as f:
		json.dump(updated_history, f, indent=2)
	print(f"Successfully saved {len(new_records)} new regulation(s) to {history_file}")

	# Send email ONLY for newly processed regulations
	df_xport = df_mini[['Agency','Proposed Rule Title',
	                    'Proposed Rule Link','Proposed Rule Posted Date',
	                    'AI Generated Comment']]
	email_sender.send_regulation_email(df_xport)

if __name__ == "__main__":
	main()
