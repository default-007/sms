from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination for most API results.
    """

    page_size = 20
    page_size_query_param = "per_page"
    max_page_size = 100


class LargeResultsSetPagination(PageNumberPagination):
    """
    Pagination for API results that might need more items per page.
    """

    page_size = 100
    page_size_query_param = "per_page"
    max_page_size = 1000
