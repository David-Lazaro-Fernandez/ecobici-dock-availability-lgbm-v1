"""``ecobici-capture``: run one capture; exit non-zero on failure so systemd logs it."""

import argparse
import logging
import sys

from ecobici.collector.capture import FEEDS, capture
from ecobici.collector.sinks import sink_from_uri

log = logging.getLogger("ecobici.capture")


def put_heartbeat(namespace: str, feed: str, ok: bool) -> None:
    """One datapoint per run; the CloudWatch alarm fires when successes stop."""
    import boto3

    boto3.client("cloudwatch").put_metric_data(
        Namespace=namespace,
        MetricData=[
            {
                "MetricName": "CaptureSuccess",
                "Dimensions": [{"Name": "Feed", "Value": feed}],
                "Value": 1.0 if ok else 0.0,
                "Unit": "Count",
            }
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", choices=sorted(FEEDS), default="station_status")
    parser.add_argument("--sink", required=True, help="s3://bucket/prefix or a local directory")
    parser.add_argument(
        "--cloudwatch-namespace",
        help="Publish a CaptureSuccess heartbeat to this CloudWatch namespace",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    ok = False
    try:
        result = capture(args.feed, sink_from_uri(args.sink))
        lag = int(result.fetched_at.timestamp()) - result.feed_last_updated
        log.info(
            "%s -> %s (stations=%s, feed lag=%ss)",
            result.feed,
            result.location,
            result.n_stations,
            lag,
        )
        ok = True
    except Exception:
        log.exception("capture of %s failed", args.feed)

    if args.cloudwatch_namespace:
        try:
            put_heartbeat(args.cloudwatch_namespace, args.feed, ok)
        except Exception:
            log.exception("heartbeat failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
