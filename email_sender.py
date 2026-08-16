import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import json

def send_regulation_email(df_xport):
    """
    Sends an email with the proposed rule and the generated comment.
    df_xport contains: Agency, Proposed Rule Title, Proposed Rule Link, Proposed Rule Posted Date, AI Generated Comment (JSON string)
    """
    sender_email = os.environ.get("SMTP_EMAIL")
    sender_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = "willsolo2k@gmail.com"

    if not sender_email or not sender_password:
        print("SMTP credentials not found in environment variables. Skipping email send.")
        return

    # If the dataframe is empty, don't send anything
    if df_xport.empty:
        print("No new regulations to email.")
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Daily Regulation Monitor: {len(df_xport)} New Proposed Rule(s)"
    msg['From'] = sender_email
    msg['To'] = receiver_email

    html_content = """
    <html>
      <head>
        <style>
          body { font-family: Arial, sans-serif; line-height: 1.6; }
          .regulation-block { border: 1px solid #ccc; padding: 15px; margin-bottom: 20px; border-radius: 5px; }
          .title { font-size: 18px; font-weight: bold; color: #333; }
          .meta { font-size: 14px; color: #666; margin-bottom: 10px; }
          .comment { background-color: #f9f9f9; padding: 10px; border-left: 4px solid #007bff; margin-top: 15px; }
          .sponsors { margin-top: 15px; }
          .sponsor-item { margin-bottom: 10px; }
        </style>
      </head>
      <body>
        <h2>New Proposed Regulations for Review</h2>
    """

    for index, row in df_xport.iterrows():
        title = row['Proposed Rule Title']
        link = row['Proposed Rule Link']
        posted_date = row['Proposed Rule Posted Date']
        agency = row['Agency']
        
        # The AI Generated Comment column now contains JSON string with structured data
        try:
            ai_data = json.loads(row['AI Generated Comment'])
            comment_text = ai_data.get('proposed_comment', 'N/A')
            sponsors = ai_data.get('sponsors', [])
        except (json.JSONDecodeError, TypeError):
            comment_text = str(row['AI Generated Comment'])
            sponsors = []

        html_content += f"""
        <div class="regulation-block">
          <div class="title"><a href="{link}">{title}</a></div>
          <div class="meta">Agency: {agency} | Posted: {posted_date}</div>
          
          <div class="comment">
            <strong>Proposed Comment / Proposal:</strong><br/>
            {comment_text.replace(chr(10), '<br>')}
          </div>
        """

        if sponsors:
            html_content += """
            <div class="sponsors">
              <strong>Potential Sponsors & Contacts:</strong>
              <ul>
            """
            for sponsor in sponsors:
                org = sponsor.get('organization_name', 'Unknown Organization')
                email_list = sponsor.get('email_contacts', [])
                email_str = ', '.join(email_list) if email_list else 'No specific emails found'
                reason = sponsor.get('reason_for_contact', '')
                html_content += f"""
                <li class="sponsor-item">
                  <strong>{org}</strong> (Emails: {email_str})<br/>
                  <em>Reason:</em> {reason}
                </li>
                """
            html_content += "</ul></div>"
        
        html_content += "</div>"

    html_content += """
      </body>
    </html>
    """

    part = MIMEText(html_content, 'html')
    msg.attach(part)

    try:
        # Assuming Gmail SMTP for this example
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    # Test block
    import pandas as pd
    test_df = pd.DataFrame([{
        'Agency': 'EPA',
        'Proposed Rule Title': 'Test Regulation',
        'Proposed Rule Link': 'https://example.com',
        'Proposed Rule Posted Date': '2023-10-01',
        'AI Generated Comment': json.dumps({
            'proposed_comment': 'This is a test comment.',
            'sponsors': [{
                'organization_name': 'Test Org',
                'email_contacts': ['contact@testorg.com'],
                'reason_for_contact': 'They care about this.'
            }]
        })
    }])
    send_regulation_email(test_df)
