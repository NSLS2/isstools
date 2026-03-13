from tiled.client import from_uri
from databroker import Broker


# test uid provided by Jorge on January 14
uid = "cb93b686-3d16-45f6-b45e-4bb3c4ec6f37"

# Create tiled client objects
client = from_uri("https://tiled.nsls2.bnl.gov")
tst_processed = client['tst/sandbox/iss/processed']

# Wrap tiled client for ISS raw data in the databroker
# backward-compatible wrapper.
db = Broker(tst_processed)


def test():
    "Load processed data and enable viewing in XView or whatever"
    print("TESTED")


if __name__ == "__main__":
    test()
