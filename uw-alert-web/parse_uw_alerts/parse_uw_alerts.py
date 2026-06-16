"""
Functions to parse UW Alerts text data and extract
key incident information in a tabular format.
"""

import os
import io
import time
import re
import pandas as pd
import openai
from transformers import GPT2Tokenizer
import googlemaps
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests


def prompt_gpt(lines, return_alert_type=False):
    """
    Arguments:
        lines - lines of text from .readlines output.
    Returns:
        A Pandas dataframe containing a structured
        table from the UW alert message chunk.
    Exceptions:
        lines must be a list of length at least 1.
        return_alert_type must be a boolean.
        The first item in lines must contain a date.
    """
    if not isinstance(lines, list):
        raise ValueError("lines must be a list")
    if len(lines) < 1:
        raise ValueError("lines must be at least length 1")
    if not isinstance(return_alert_type, bool):
        raise ValueError("return_alert_type must be a boolean")
    if re.match(r"^[A-z]+\s\d{1,2},\s\d{4}", lines[0]) is None:
        raise ValueError("First item in lines must contain a date")

    gpt_task = (
        "Extract a markdown table with the columns Date (mm/dd/yyyy),"
        " Report Time (hh:mm AM/PM), Incident Time (hh:mm AM/PM),"
        " Nearest Address to Incident, Incident Category, and"
        " Incident Summary from the following alert message.\n"
        'Text: """'
    )
    alert_chunk = "\n".join(line for line in lines if not line.isspace())
    alert_chunk = alert_chunk.strip("\n")
    alert_chunk = re.sub(r"\u2013|\u2014", "-", alert_chunk)
    gpt_prompt = "\n".join([gpt_task, alert_chunk])
    gpt_prompt += '"""'
    tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
    n_tokens = len(tokenizer(gpt_prompt)["input_ids"])
    response = openai.Completion.create(
        engine="text-davinci-003", prompt=gpt_prompt, max_tokens=4097 - n_tokens
    )
    gpt_table = pd.read_table(
        io.StringIO(response["choices"][0]["text"]),
        sep="|",
        skipinitialspace=True,
        header=0,
        index_col=False,
    )
    gpt_table.drop(list(gpt_table.filter(regex="Unnamed")), axis=1, inplace=True)
    column_names = [
        "Date",
        "Report Time",
        "Incident Time",
        "Nearest Address to Incident",
        "Incident Category",
        "Incident Summary",
    ]
    gpt_table.columns = column_names
    if re.match(r"(:)?--", gpt_table["Date"].values[0]):
        gpt_table = gpt_table.iloc[1:]
    gpt_table.reset_index(inplace=True)
    gpt_table = gpt_table.loc[:, column_names]
    alert_chunk = alert_chunk.split("\n")
    alert_chunk = [line for line in alert_chunk if not line.isspace()]
    alert_chunk = alert_chunk[1:]
    alert_chunk = "\n".join(alert_chunk)
    gpt_table["Incident Alert"] = alert_chunk.strip("\n")
    alert_type = "Original"
    for line in lines:
        if re.match(r"(\[)?update(d)?(:|\s+)", line, re.IGNORECASE):
            alert_type = "Update"
    gpt_table["Alert Type"] = alert_type
    for column in column_names:
        gpt_table[column] = gpt_table[column].astype(str).str.strip()
    time.sleep(5)
    if return_alert_type:
        return (gpt_table, alert_type)
    return gpt_table


def generate_ids(uw_alert_file, gpt_table, alert_type, parsing=False):
    """
    Arguments:
        uw_alert_file - either a filepath to csv file or Pandas DataFrame.
        gpt_table - Pandas DataFrame of GPT output.
        alert_type - string either 'Update' or 'Original'.
        parsing - Boolean for if function call is to parse .txt file.
    Returns:
        A Pandas DataFrame where gpt_table has added columns
        containing the incident and alert ids.
    Exceptions:
        uw_alert_file must be a filepath with .csv extension or
        a Pandas DataFrame.
        gpt_table must be a Pandas DataFrame.
    """
    if not isinstance(uw_alert_file, str):
        if not isinstance(uw_alert_file, pd.DataFrame):
            raise ValueError("uw_alert_file must be a filepath or Pandas DataFrame")
        clean_data = uw_alert_file.copy()
    else:
        if not re.search(".csv$", uw_alert_file):
            raise ValueError("uw_alert_file must be a .csv filepath")
        clean_data = pd.read_csv(uw_alert_file, index_col=False)
    if not isinstance(gpt_table, pd.DataFrame):
        raise ValueError("gpt_table must be a filepath or Pandas DataFrame")
    if len(gpt_table.index) == 0:
        raise ValueError("gpt_table must have at least 1 row")
    if alert_type not in ["Update", "Original"]:
        raise ValueError("alert_type must be either 'Update' or 'Original'")
    if not isinstance(parsing, bool):
        raise ValueError("parsing must be a boolean")

    if len(clean_data.index) == 0:
        gpt_table["Incident ID"] = 1
        gpt_table["Alert ID"] = 1
        return gpt_table
    gpt_table["Alert ID"] = clean_data["Alert ID"].max() + 1
    if parsing:
        if clean_data["Alert Type"].values[-1] == "Original":
            gpt_table["Incident ID"] = clean_data["Incident ID"].values[-1] + 1
            return pd.concat([clean_data, gpt_table], ignore_index=True)
        gpt_table["Incident ID"] = clean_data["Incident ID"].values[-1]
        return pd.concat([clean_data, gpt_table], ignore_index=True)
    if gpt_table["Alert Type"].values[0] == "Update":
        gpt_table["Incident ID"] = clean_data["Incident ID"].values[0]
        return gpt_table
    gpt_table["Incident ID"] = clean_data["Incident ID"].max() + 1
    return gpt_table


def generate_csv(out_filepath, lines):
    """
    Arguments:
        out_filepath - path to .csv file storing GPT output.
        lines - lines of text from .readlines output.
    Returns:
        None.
    Exceptions:
        out_filepath must be a string with .csv extension.
        lines must be a list of length at least 1.
    """
    if not isinstance(out_filepath, str):
        raise ValueError("filepath must be a string")
    if re.search(r"\.csv$", out_filepath) is None:
        raise ValueError("filepath must have a .csv extension")
    if not isinstance(lines, list):
        raise ValueError("lines must be a list")
    if len(lines) < 1:
        raise ValueError("lines must be at least length 1")
    if lines[0] == lines[1]:
        lines = lines[1:]
    gpt_table = prompt_gpt(lines, return_alert_type=True)
    alert_type = gpt_table[1]
    gpt_table = gpt_table[0]
    clean_data = generate_ids(out_filepath, gpt_table, alert_type, parsing=True)
    clean_data.to_csv(out_filepath, index=False)
    return "CSV generated"


def parse_txt_data(filepath, out_filepath, file_start=0):
    """
    Arguments:
        filepath - path to .txt file containing historial UW Alerts blogposts.
        out_filepath - path to .csv file storing GPT output.
        file_start - int representing index at which parsing should start.
    Returns:
        None.
    Exceptions:
        filepath must be a string with .txt extension.
        out_filepath must be a string with .csv extension.
        file_start must be an integer 0 or greater.
        Invalid inputs throw ValueError exceptions.
    """
    if not isinstance(filepath, str):
        raise ValueError("filepath must be a string")
    if re.search(r"\.txt$", filepath) is None:
        raise ValueError("filepath must have a .txt extension")
    if not isinstance(out_filepath, str):
        raise ValueError("filepath must be a string")
    if re.search(r"\.csv$", out_filepath) is None:
        raise ValueError("filepath must have a .csv extension")
    if not isinstance(file_start, int) or file_start < 0:
        raise ValueError("file_start must be an integer 0 or greater")

    if file_start == 0:
        columns = [
            "Date",
            "Report Time",
            "Incident Time",
            "Nearest Address to Incident",
            "Incident Category",
            "Incident Summary",
            "Incident Alert",
            "Incident ID",
            "Alert ID",
        ]
        empty_file = pd.DataFrame({column: [] for column in columns})
        empty_file.to_csv(out_filepath, index=False)
    with open(filepath, encoding="UTF-8") as file:
        lines = file.readlines()
        last_date = None
        last_event = None
        last_event_index = None
        for i, line in enumerate(lines[file_start:]):
            if (i + file_start) == (len(lines) - 1):
                generate_csv(out_filepath, [last_date] + lines[last_event_index:])
            date_check = re.match(r"^[A-z]+\s\d{1,2},\s\d{4}", line)
            if date_check:
                if last_event is not None:
                    alert_end = i + file_start
                    generate_csv(
                        out_filepath, [last_date] + lines[last_event_index:alert_end]
                    )
                last_date = line
                last_event = "date"
                last_event_index = i + file_start
            if re.match(r"(\[)?update(d)?(:|\s+)", line, re.IGNORECASE) or re.match(
                r"(\[)?original (post)?", line, re.IGNORECASE
            ):
                alert_end = i + file_start
                if last_event == "original/update":
                    generate_csv(
                        out_filepath, [last_date] + lines[last_event_index:alert_end]
                    )
                last_event = "original/update"
                last_event_index = i + file_start
    return "Parsing complete"


def clean_gpt_output(gpt_output="../data/uw_alerts_gpt.csv", gmaps_client=None):
    """
    Arguments:
        gpt_output - either a filepath to csv file or Pandas DataFrame.
    Returns:
        A Pandas DataFrame with cleaned columns.
    Exceptions:
        gpt_output must be a filepath with .csv extension or
        a Pandas DataFrame.
        ValueError will be thrown otherwise.
    """
    if not isinstance(gpt_output, str):
        if not isinstance(gpt_output, pd.DataFrame):
            raise ValueError("gpt_output must be a filepath or Pandas DataFrame")
        gpt_data = gpt_output.copy()
    else:
        if not re.search(".csv$", gpt_output):
            raise ValueError("gpt_output must be a .csv filepath")
        gpt_data = pd.read_csv(gpt_output, index_col=False)
    if len(gpt_data.index) == 0:
        raise ValueError("gpt_ouput must have at least 1 row")
    if not isinstance(gmaps_client, googlemaps.Client):
        raise ValueError("gmaps_client must be a Google Maps Client")
    gpt_data["Date"] = pd.to_datetime(
        gpt_data["Date"], infer_datetime_format=True, errors="coerce"
    )
    gpt_data["Date"] = gpt_data.groupby(["Incident ID"], sort=False)["Date"].bfill()
    gpt_data["Date"] = gpt_data["Date"].dt.date
    for column in ["Report Time", "Incident Time"]:
        gpt_data[column] = gpt_data[column].str.upper()
        gpt_data[column] = gpt_data[column].str.strip()
        gpt_data[column] = pd.to_datetime(
            gpt_data[column], infer_datetime_format=True, errors="coerce"
        )
        gpt_data[column] = gpt_data.groupby(["Incident ID"], sort=False)[column].bfill()
        gpt_data[column] = gpt_data[column].dt.time
    gpt_data["Incident Alert"] = gpt_data["Incident Alert"].str.strip()
    gpt_data["Nearest Address to Incident"] = gpt_data[
        "Nearest Address to Incident"
    ].str.replace(r"^\-$", "", regex=True)
    gpt_data["Nearest Address to Incident"] = gpt_data.groupby(
        ["Incident ID"], sort=False
    )["Nearest Address to Incident"].bfill()
    gpt_data[["Nearest Address to Incident"]] = gpt_data[
        ["Nearest Address to Incident"]
    ].fillna("")
    geocode_results = [
        gmaps_client.geocode("".join([address, ", University District, Seattle WA"]))
        for address in gpt_data["Nearest Address to Incident"]
    ]
    gpt_data["Google Address"] = [
        result[0]["formatted_address"] for result in geocode_results
    ]
    gpt_data["geometry"] = [result[0]["geometry"] for result in geocode_results]
    return gpt_data


def scrape_uw_alerts(uw_alert_filepath="../data/uw_alerts_clean.csv"):
    """
    Arguments:
        uw_alert_filepath - string containing filepath to clean UW Alerts data
    Returns:
        If a new alert was made, returns a Pandas DataFrame.
        Otherwise, returns None.
    Exceptions:
        uw_alert_filepath must be a string with .csv extension.
    """
    if not isinstance(uw_alert_filepath, str):
        raise ValueError("uw_alert_filepath must be a string")
    if re.search(r"\.csv$", uw_alert_filepath) is None:
        raise ValueError("uw_alert_filepath must have a .csv extension")
    load_dotenv("../.env")
    openai.api_key = os.getenv("OPENAI_API_KEY")
    gmaps_client = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))
    uw_alerts = pd.read_csv(uw_alert_filepath, index_col=False)
    last_alert = uw_alerts["Incident Alert"].values[0]

    url = "https://emergency.uw.edu/"
    page = requests.get(url, timeout=10)
    soup = BeautifulSoup(page.content, "html.parser")
    main_content = soup.find(id="main_content")
    p_tags = main_content.find_all("p")
    for para in p_tags:
        if re.search(r"^[A-z]+\s\d{1,2},\s\d{4}", para.text):
            newest_alert_list = [para.text for para in p_tags[:2]]
            break
    newest_alert_list[1] = re.sub(r"\u2013|\u2014", "-", newest_alert_list[1])
    if not re.search(last_alert, newest_alert_list[1]):
        gpt_output = prompt_gpt(newest_alert_list, return_alert_type=True)
        gpt_table = generate_ids(uw_alerts, gpt_output[0], gpt_output[1])
        gpt_table = clean_gpt_output(gpt_output=gpt_table, gmaps_client=gmaps_client)
        uw_alerts = pd.concat([gpt_table, uw_alerts], ignore_index=True)
        uw_alerts = clean_gpt_output(gpt_output=uw_alerts, gmaps_client=gmaps_client)
        uw_alerts.to_csv(uw_alert_filepath, index=False)
        return gpt_table
    return None


if __name__ == "__main__":
    load_dotenv("../.env")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
    FILEPATH = "../data/UW_Alerts_2018_2022.txt"
    OUT_FILEPATH = "../data/uw_alerts_gpt.csv"
    CLEAN_FILEPATH = "../data/uw_alerts_clean.csv"
    FILE_START = 0
    openai.api_key = OPENAI_API_KEY
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
