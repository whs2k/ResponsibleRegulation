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
	regulation_api_key = args.regulation_api_key

	url = 'https://api.regulations.gov/v4/documents?filter[agencyId]=EPA&filter[documentType]=Proposed%20Rule&sort=-postedDate&api_key={}'.format(regulation_api_key)
	df_output = helper.create_dataframe_from_list_of_dicts(requests.get(url).json()['data'])
	df_output['Agency']='EPA'
	df_output['Proposed Rule Link'] = 'https://www.regulations.gov/document/' + df_output.id
	df_output['Proposed Rule Title'] = df_output['attributes.title']
	df_output['Proposed Rule Posted Date'] = df_output['attributes.postedDate']
	df_mini = df_output.head(3)
	#print(df_mini)
	df_mini['AI Generated Comment'] = df_mini['id'].apply(lambda x: helper.generate_comment(
	    proposed_rule_id_=x, gemini_client=authenticated_gemini_client, 
	    regulation_api_key_=regulation_api_key, sleep_seconds=30))

	df_xport = df_mini[['Agency','Proposed Rule Title',
	                    'Proposed Rule Link','Proposed Rule Posted Date',
	                    'AI Generated Comment']]
	html_string = helper.dataframe_to_mdb_html(df_xport)

	with open("index.html", "w") as f:
	    f.write(html_string)

if __name__ == "__main__":
	main()
