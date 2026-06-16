"""
Tests for parse_uw_alerts.py
"""

import os
import unittest
import pandas as pd

# pylint: disable=import-error
# pylint: disable=no-name-in-module
# pylint: disable=pointless-string-statement
from parse_uw_alerts.parse_uw_alerts import (
    prompt_gpt,
    generate_ids,
    parse_txt_data,
    clean_gpt_output,
    generate_csv,
    scrape_uw_alerts,
)


class TestParseUWAlertsPromptGPT(unittest.TestCase):
    """
    Test methods for prompt_gpt function.
    """

    def test_prompt_list(self):
        """Test for lines being a list"""
        with self.assertRaises(ValueError):
            prompt_gpt("not a line")

    def test_prompt_list_length(self):
        """Test for lines having at least 1 item"""
        with self.assertRaises(ValueError):
            prompt_gpt([])

    def test_prompt_list_none(self):
        """Test for lines being None"""
        with self.assertRaises(ValueError):
            prompt_gpt(None)

    def test_prompt_bool(self):
        """Test for return_alert_type being boolean"""
        with self.assertRaises(ValueError):
            prompt_gpt(["October 21, 2019\n", "UW Alert"], return_alert_type="yes")

    def test_prompt_bool2(self):
        """Test for return_alert_type being boolean"""
        with self.assertRaises(ValueError):
            prompt_gpt(["October 21, 2019\n", "UW Alert"], return_alert_type="no")

    def test_prompt_date_check(self):
        """Test for first item in lines containing a date"""
        with self.assertRaises(ValueError):
            prompt_gpt(["not a date\n", "alert"])

    """
    The test below is commented out because it requires
    API keys. Github's build tests fail because our project
    gitignores the .env containing the API keys.
    When running coverage locally with the following test
    included, we obtain an overall coverage of 92%.
    """
    # def test_prompt_gpt_test_output(self):
    #     """Test GPT output"""
    #     load_dotenv('../.env')
    #     openai.api_key = os.getenv('OPENAI_API_KEY')
    #     test_prompt = ['March 9, 2023\n', 'UPDATE at 8:47pm: Random alert.']
    #     expected_result = pd.DataFrame({
    #         'Date': ['03/09/2023'],
    #         'Alert Type': ['Update']
    #     })
    #     gpt_table = prompt_gpt(test_prompt)
    #     pdt.assert_frame_equal(gpt_table[['Date', 'Alert Type']],
    #                            expected_result)


class TestParseUWAlertsGenerateIds(unittest.TestCase):
    """
    Test methods for generate_ids function.
    """

    def test_gen_id_filepath(self):
        """Test for string filepath"""
        with self.assertRaises(ValueError):
            generate_ids(
                uw_alert_file=1,
                gpt_table=pd.DataFrame({"Test": [1]}),
                alert_type="Update",
            )

    def test_gen_id_filepath_csv(self):
        """Test for .csv filepath"""
        dirname = os.path.dirname(__file__)
        file_path = os.path.join(dirname, "../../data/output.txt")
        with self.assertRaises(ValueError):
            generate_ids(
                uw_alert_file=file_path,
                gpt_table=pd.DataFrame({"Test": [1]}),
                alert_type="Update",
            )

    def test_gen_id_dataframe(self):
        """Test for Pandas DataFrame input"""
        dirname = os.path.dirname(__file__)
        file_path = os.path.join(dirname, "../../data/uw_alerts_gpt.csv")
        with self.assertRaises(ValueError):
            generate_ids(uw_alert_file=file_path, gpt_table=[1], alert_type="Update")

    def test_gen_id_dataframe_len(self):
        """Test for DataFrame of at least 1 row"""
        dirname = os.path.dirname(__file__)
        file_path = os.path.join(dirname, "../../data/uw_alerts_gpt.csv")
        with self.assertRaises(ValueError):
            generate_ids(
                uw_alert_file=file_path, gpt_table=pd.DataFrame(), alert_type="Update"
            )

    def test_gen_id_dataframe_alert_type(self):
        """Test for string alert_type being 'Update' or 'Original'"""
        dirname = os.path.dirname(__file__)
        file_path = os.path.join(dirname, "../../data/uw_alerts_gpt.csv")
        with self.assertRaises(ValueError):
            generate_ids(
                uw_alert_file=file_path,
                gpt_table=pd.DataFrame({"Test": [1]}),
                alert_type="Random",
            )

    def test_gen_id_parsing(self):
        """Test for requiring boolean parsing"""
        dirname = os.path.dirname(__file__)
        file_path = os.path.join(dirname, "../../data/uw_alerts_gpt.csv")
        with self.assertRaises(ValueError):
            generate_ids(
                uw_alert_file=file_path,
                gpt_table=pd.DataFrame({"Test": [1]}),
                alert_type="Update",
                parsing="yes",
            )

    """
    The test below is commented out because it requires
    API keys. Github's build tests fail because our project
    gitignores the .env containing the API keys.
    When running coverage locally with the following test
    included, we obtain an overall coverage of 92%.
    """
    # def test_gen_id_output(self):
    #     """Test for generate_ids output"""
    #     dirname = os.path.dirname(__file__)
    #     file_path = os.path.join(dirname, "../../data/uw_alerts_gpt.csv")
    #     gpt_table = pd.DataFrame({
    #         'Alert Type': ['Original']
    #     })
    #     clean_file = pd.read_csv(file_path, index_col=False)
    #     max_alert_id = max(clean_file['Alert ID'].values)
    #     max_incident_id = max(clean_file['Incident ID'].values)
    #     expected_output = pd.DataFrame({
    #         'Alert ID': [max_alert_id+1],
    #         'Incident ID': [max_incident_id+1]
    #     })
    #     gen_id_output = generate_ids(uw_alert_file=file_path,
    #                                  gpt_table=gpt_table,
    #                                  alert_type=gpt_table[
    #         'Alert Type'].values[0],
    #                                  parsing=False)
    #     gen_id_output = gen_id_output[['Alert ID',
    #                                    'Incident ID']]
    #     pdt.assert_frame_equal(gen_id_output.reset_index(drop=True),
    #                            expected_output.reset_index(drop=True))


class TestParseUWAlertsGenerateCSV(unittest.TestCase):
    """
    Test methods for generate_csv function.
    """

    def test_gen_csv_filepath(self):
        """Test for string filepath"""
        with self.assertRaises(ValueError):
            generate_csv(out_filepath=1, lines=["1", "2"])

    def test_gen_csv_filepath_csv(self):
        """Test for string .csv filepath"""
        with self.assertRaises(ValueError):
            generate_csv(out_filepath="../data/output.txt", lines=["1", "2"])

    def test_gen_csv_list(self):
        """Test for lines being a list"""
        with self.assertRaises(ValueError):
            generate_csv(out_filepath="../data/uw_alerts_gpt.csv", lines=1)

    def test_gen_csv_list_length(self):
        """Test for lines having at least 1 item"""
        with self.assertRaises(ValueError):
            generate_csv(out_filepath="../data/uw_alerts_gpt.csv", lines=[])

    """
    The test below is commented out because it requires
    API keys. Github's build tests fail because our project
    gitignores the .env containing the API keys.
    When running coverage locally with the following test
    included, we obtain an overall coverage of 92%.
    """
    # def test_gen_csv_list_length(self):
    #     """Test for generate_csv output"""
    #     load_dotenv('../.env')
    #     openai.api_key = os.getenv('OPENAI_API_KEY')
    #     text_txt = '../data/UW_Alerts_TEST.txt'
    #     out_filepath = '../data/uw_alerts_gpt_TEST.csv'
    #     with open(text_txt, encoding='UTF-8') as file:
    #         lines = file.readlines()
    #     test_output = generate_csv(out_filepath=out_filepath,
    #                                lines=lines)
    #     self.assertEqual(test_output, 'CSV generated')


class TestParseUWAlertsParseTxtData(unittest.TestCase):
    """
    Test methods for parse_txt_data function.
    """

    def test_txt_extension(self):
        """Test for requiring .txt input"""
        with self.assertRaises(ValueError):
            parse_txt_data(
                "../data/UW_Alerts_2018_2022.csv",
                out_filepath="../data/uw_alerts_gpt.csv",
            )

    def test_txt_extension_csv(self):
        """Test for requiring .txt input"""
        with self.assertRaises(ValueError):
            parse_txt_data(
                filepath="../data/UW_Alerts_2018_2022.txt",
                out_filepath="../data/uw_alerts_gpt.txt",
            )

    def test_txt_extension_fp_str(self):
        """Test for requiring string input"""
        with self.assertRaises(ValueError):
            parse_txt_data(filepath=1, out_filepath="../data/uw_alerts_gpt.csv")

    def test_txt_extension_out_str(self):
        """Test for requiring string output"""
        with self.assertRaises(ValueError):
            parse_txt_data(filepath="../data/UW_Alerts_2018_2022.txt", out_filepath=1)

    def test_txt_file_start_int(self):
        """Test for requiring integer file_start"""
        with self.assertRaises(ValueError):
            parse_txt_data(
                filepath="../data/UW_Alerts_2018_2022.txt",
                out_filepath="../data/uw_alerts_gpt.csv",
                file_start="1",
            )

    def test_txt_file_start_zero_or_greater(self):
        """Test for requiring file_start >= 0"""
        with self.assertRaises(ValueError):
            parse_txt_data(
                filepath="../data/UW_Alerts_2018_2022.txt",
                out_filepath="../data/uw_alerts_gpt.csv",
                file_start=-1,
            )

    """
    The test below is commented out because it requires
    API keys. Github's build tests fail because our project
    gitignores the .env containing the API keys.
    When running coverage locally with the following test
    included, we obtain an overall coverage of 92%.
    """
    # def test_txt_file_output(self):
    #     """Test for parse_txt_data output"""
    #     load_dotenv('../.env')
    #     openai.api_key = os.getenv('OPENAI_API_KEY')
    #     filepath = '../data/UW_Alerts_TEST.txt'
    #     out_filepath = '../data/uw_alerts_gpt_TEST.csv'
    #     test_output = parse_txt_data(filepath=filepath,
    #                                  out_filepath=out_filepath)
    #     self.assertEqual(test_output, 'Parsing complete')


class TestParseUWAlertsCleanGPTOutput(unittest.TestCase):
    """
    Test methods for clean_gpt_output function.
    """

    def test_clean_gpt_gmaps_client2(self):
        """Test for requiring Google Maps Client"""
        with self.assertRaises(ValueError):
            clean_gpt_output(gpt_output=pd.DataFrame(), gmaps_client="random_key")

    def test_clean_gpt_gmaps_client3(self):
        """Test for requiring Google Maps Client"""
        with self.assertRaises(ValueError):
            clean_gpt_output(gpt_output=pd.DataFrame(), gmaps_client=123)

    """
    The tests below is commented out because it requires
    API keys. Github's build tests fail because our project
    gitignores the .env containing the API keys.
    When running coverage locally with the following test
    included, we obtain an overall coverage of 92%.
    """
    # def test_clean_gpt_csv_fp(self):
    #     """Test for requiring .csv filepath"""
    #     load_dotenv('../.env')
    #     gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))
    #     with self.assertRaises(ValueError):
    #         clean_gpt_output(gpt_output='test.txt', gmaps_client=gmaps)
    # def test_clean_gpt_gmaps_client(self):
    #     """Test for requiring Google Maps Client"""
    #     with self.assertRaises(ValueError):
    #         clean_gpt_output(gpt_output=pd.DataFrame(), gmaps_client=None)
    # def test_clean_gpt_test_clean_output(self):
    #     """Test clean GPT output"""
    #     load_dotenv('../.env')
    #     gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))
    #     gpt_clean = clean_gpt_output(gmaps_client=gmaps).tail(1)
    #     gpt_clean = gpt_clean[['Nearest Address to Incident',
    #                                       'Alert Type',
    #                                       'Google Address']]
    #     expected_result = pd.DataFrame({
    #         'Nearest Address to Incident': ['5200 Block of 20th Ave. NE'],
    #         'Alert Type': ['Original'],
    #         'Google Address': ['5200 20th Ave NE, Seattle, WA 98105, USA']
    #     })
    #     pdt.assert_frame_equal(gpt_clean.reset_index(drop=True),
    #                            expected_result.reset_index(drop=True))
    # def test_clean_gpt_df(self):
    #     """Test for requiring Pandas DataFrame input"""
    #     load_dotenv('../.env')
    #     gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))
    #     with self.assertRaises(ValueError):
    #         clean_gpt_output(gpt_output=[1,2,3], gmaps_client=gmaps)


class TestParseUWAlertsScrapeUWAlerts(unittest.TestCase):
    """
    Test methods for scrape_uw_alerts function.
    """

    def test_scrape_uw_alerts_csv_fp(self):
        """Test for requiring .csv filepath"""
        with self.assertRaises(ValueError):
            scrape_uw_alerts(uw_alert_filepath="../data/uw_alerts_clean.txt")

    def test_scrape_uw_alerts_str_fp(self):
        """Test for requiring string filepath"""
        with self.assertRaises(ValueError):
            scrape_uw_alerts(uw_alert_filepath=1)

    """
    The test below is commented out because it requires
    API keys. Github's build tests fail because our project
    gitignores the .env containing the API keys.
    When running coverage locally with the following test
    included, we obtain an overall coverage of 92%.
    """
    # def test_scrape_uw_alerts_output(self):
    #     """Test for scrape_uw_alerts output"""
    #     dirname = os.path.dirname(__file__)
    #     file_path = os.path.join(dirname,
    #                              "../../data/uw_alerts_clean_TEST.csv")
    #     scrape_output = scrape_uw_alerts(uw_alert_filepath=file_path)
    #     clean_test_file = pd.read_csv(file_path, index_col=False)
    #     clean_test_file = clean_test_file.head(1)
    #     try:
    #         self.assertEqual(scrape_output, None)
    #     except AssertionError:
    #         pdt.assert_frame_equal(scrape_output.reset_index(drop=True),
    #                                clean_test_file.reset_index(drop=True))


if __name__ == "__main__":
    unittest.main()
