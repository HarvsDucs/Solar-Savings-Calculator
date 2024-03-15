import os
import pathlib
from dotenv import load_dotenv

import requests
from flask import Flask, session, abort, redirect, request, render_template
from flask_cors import CORS
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests


load_dotenv()
app = Flask(__name__)
CORS(app)

app.secret_key = os.environ["app_secret_key"] # make sure this matches with that's in client_secret.json

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" # to allow Http traffic for local dev

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")

OAUTHLIB_INSECURE_TRANSPORT = os.environ.get("OAUTHLIB_INSECURE_TRANSPORT")
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"
)


def login_is_required(function):
    def wrapper(*args, **kwargs):
        if "google_id" not in session:
            return abort(401)  # Authorization required
        else:
            return function()

    return wrapper


@app.route("/login")
def login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route('/calculate', methods=['POST', 'GET'])
def calculate():
  if request.method == 'POST':
        print("calculated")
        selected_bill = float(request.form['selected_bill'])
        address = request.form['address']
        api_key = os.environ.get('solar_api_key')

        # List of electric bill values
        bill_values = [40, 45, 50, 60, 70, 80, 90, 100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 450, 500]

        # Calculate index for financial analysis based on selected bill
        if selected_bill in bill_values:
            i = bill_values.index(selected_bill)
            print(f"Index of the selected bill (${selected_bill}): {i}")
        else:
            print("Selected bill is not in the list.")

        # Geocoding API request
        geocode_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={api_key}"
        geocode_response = requests.get(geocode_url)

        if geocode_response.status_code == 200:
            geocode_data = geocode_response.json()
            location = geocode_data["results"][0]["formatted_address"]
            latitude = geocode_data["results"][0]["geometry"]["location"]["lat"]
            longitude = geocode_data["results"][0]["geometry"]["location"]["lng"]

            # Solar API request
            solar_api_url = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
            params = {
                'location.latitude': latitude,
                'location.longitude': longitude,
                'key': api_key
            }
            solar_response = requests.get(solar_api_url, params=params)

            if solar_response.status_code == 200:
                solar_data = solar_response.json()

                # Assuming 'i' is correctly determined by your logic; you might need to adjust this based on actual API response structure
                # Displaying results from the solar potential data
                monthly_bill_units = solar_data["solarPotential"]["financialAnalyses"][i]["monthlyBill"]["units"]
                print(f"Monthly Electric Bill: ${monthly_bill_units}")

                rebate_value_units = solar_data["solarPotential"]["financialAnalyses"][i]["cashPurchaseSavings"]["rebateValue"]["units"]
                print(f"#### Cash Paid Rebate Value: ${rebate_value_units}")

                savings_year1_units = solar_data["solarPotential"]["financialAnalyses"][i]["financedPurchaseSavings"]["savings"]["savingsYear1"]["units"]
                print(f"#### Savings after 1 year: ${savings_year1_units}")

                savings_year20_units = solar_data["solarPotential"]["financialAnalyses"][i]["financedPurchaseSavings"]["savings"]["savingsYear20"]["units"]
                print(f"#### Savings after 20 years: ${savings_year20_units}")

                result = {
                "selected_bill" : selected_bill,
                "address": address,
                "cash_paid_rebate_value": rebate_value_units,
                "calculated_savings_after_1_year": savings_year1_units,
                "calculated_savings_after_20_years": savings_year20_units
                }

                return render_template('results.html', result = result)

            else:
                print("Failed to retrieve solar savings data.")
        else:
            print("Failed to geocode address. Please check the address and try again.")


@app.route("/callback")
def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    session["email"] = id_info.get("email")
    return redirect("/protected_area")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/")
def index():
    return render_template('index.html')


@app.route("/protected_area")
@login_is_required
def protected_area():
    stored_data = []

    # Iterate over the session object and store key-value pairs in a list
    for key, value in session.items():
        stored_data.append({"key": key, "value": value})
    return f"Hello {session['name']}! {stored_data} <br/> <a href='/logout'><button>Logout</button></a>"


if __name__ == "__main__":
    app.run(debug=True)