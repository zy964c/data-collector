def test_hide_credentials():
    url_without_password = "rtsp://10.10.10.10:554/Streaming/Channels/101"
    url_with_password = "rtsp://admin:admin@10.10.10.10:554/Streaming/Channels/101"
    domain_url_with_password = "rtsp://admin:admin@domain.ru:554/Streaming/Channels/101"
    masked_ip = "rtsp://*:*@10.10.10.10:554/Streaming/Channels/101"
    masked_domain = "rtsp://*:*@domain.ru:554/Streaming/Channels/101"
    from exceptions.exceptions import CollectorError

    exception = CollectorError(detail=f"Error in url {url_without_password}")
    assert str(exception) == f"Error in url {url_without_password}"
    exception = CollectorError(detail=f"Error in url {url_with_password}")
    assert str(exception) == f"Error in url {masked_ip}"
    exception = CollectorError(detail=f"Error in url {domain_url_with_password}")
    assert str(exception) == f"Error in url {masked_domain}"
