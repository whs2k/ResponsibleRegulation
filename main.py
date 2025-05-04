import helper
import pandas as pd
import requests
import argparse
from google import genai


def main():
	# Create an ArgumentParser object
	parser = argparse.ArgumentParser(description="A sample program to demonstrate argument parsing")

	# Add named arguments
	parser.add_argument("--regulation_api_key", type=str, help="https://open.gsa.gov/api/regulationsgov/")
	parser.add_argument("--gemini_api_key", type=str, help="https://ai.google.dev/gemini-api/docs/api-key")

	# Parse the arguments
	args = parser.parse_args()
	#print(args.regulation_api_key)

	authenticated_gemini_client = genai.Client(api_key=args.gemini_api_key)

	url = 'https://api.regulations.gov/v4/documents?filter[agencyId]=EPA&filter[documentType]=Proposed%20Rule&sort=-postedDate&api_key=jjRAC6upzdHbWRi7H1bhYbC2zsIiEXZHRScdKS0t'
	df_output = helper.create_dataframe_from_list_of_dicts(requests.get(url).json()['data'])
	df_mini = df_output.head(3)
	df_mini['comment'] = df_mini['id'].apply(lambda x: helper.generate_comment(
    	proposed_rule_id_=x, gemini_client=authenticated_gemini_client, 
    	regulation_api_key_=args.regulation_api_key, sleep_seconds=30))

	df_xport = df_mini[['id','comment','links.self']]
	html_string = helper.dataframe_to_mdb_html(df_xport)

	with open("index.html", "w") as f:
	    f.write(html_string)

if __name__ == "__main__":
	main()
