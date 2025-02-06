from pyactiveresource.collection import Collection


class PaginatedCollection(Collection):
    """
    A subclass of Collection that supports cursor-based pagination.

    Attributes:
        next_page_url (str): URL to fetch the next page of data.
        previous_page_url (str): URL to fetch the previous page of data.
        metadata (dict): Metadata containing pagination information.
    """

    def __init__(self, *args, **kwargs):
        """
        Initializes PaginatedCollection, handling metadata and pagination URLs.
        
        If a Collection object is passed, its metadata is inherited.
        """
        metadata = kwargs.pop("metadata", None)
        obj = args[0]
        if isinstance(obj, Collection):
            metadata = metadata or obj.metadata
            if metadata:
                metadata.update(obj.metadata)
            super().__init__(obj, metadata=metadata)
        else:
            super().__init__(metadata=metadata or {}, *args, **kwargs)

        self._check_resource_class()
        self.metadata["pagination"] = self._parse_pagination()
        self.next_page_url = self.metadata["pagination"].get("next")
        self.previous_page_url = self.metadata["pagination"].get("previous")

        self._next = None
        self._previous = None
        self._current_iter = None
        self._no_iter_next = kwargs.pop("no_iter_next", True)

    def _check_resource_class(self):
        """Ensures the 'resource_class' attribute is present in the metadata."""
        if "resource_class" not in self.metadata:
            raise AttributeError('Cursor-based pagination requires a "resource_class" attribute in the metadata.')

    def _parse_pagination(self):
        """Parses pagination links from the headers in metadata."""
        headers = self.metadata.get("headers", {})
        link_header = headers.get("Link") or headers.get("link")
        if not link_header:
            return {}

        result = {}
        for value in link_header.split(", "):
            link, rel = value.split("; ")
            result[rel.split('"')[1]] = link[1:-1]
        return result

    def has_previous_page(self):
        """Checks if the current page has a previous page."""
        return bool(self.previous_page_url)

    def has_next_page(self):
        """Checks if the current page has a next page."""
        return bool(self.next_page_url)

    def previous_page(self, no_cache=False):
        """
        Returns the previous page of items.

        Args:
            no_cache (bool): If True, the page will not be cached.
        
        Returns:
            PaginatedCollection: The previous page of data.
        """
        if self._previous:
            return self._previous
        if not self.has_previous_page():
            raise IndexError("No previous page")
        return self._fetch_page(self.previous_page_url, no_cache)

    def next_page(self, no_cache=False):
        """
        Returns the next page of items.

        Args:
            no_cache (bool): If True, the page will not be cached.
        
        Returns:
            PaginatedCollection: The next page of data.
        """
        if self._next:
            return self._next
        if not self.has_next_page():
            raise IndexError("No next page")
        return self._fetch_page(self.next_page_url, no_cache)

    def _fetch_page(self, url, no_cache=False):
        """Fetches a page by URL and handles caching."""
        next_page = self.metadata["resource_class"].find(from_=url)
        if not no_cache:
            self._next = next_page
            self._next._previous = self
        next_page._no_iter_next = self._no_iter_next
        return next_page

    def __iter__(self):
        """Iterates through items, fetching additional pages if necessary."""
        for item in super().__iter__():
            yield item

        if self._no_iter_next:
            return

        try:
            if not self._current_iter:
                self._current_iter = self
            self._current_iter = self.next_page()

            for item in self._current_iter:
                yield item
        except IndexError:
            return

    def __len__(self):
        """Returns the total number of items across all pages."""
        count = len(self._next) if self._next else 0
        return count + super().__len__()


class PaginatedIterator:
    """
    An iterator over paginated collections that is memory-efficient by keeping
    only one page in memory at a time.

    Usage:
        from shopify import Product, PaginatedIterator
        for page in PaginatedIterator(Product.find()):
            for item in page:
                do_something(item)
    """

    def __init__(self, collection):
        """
        Initializes the PaginatedIterator with a PaginatedCollection.

        Args:
            collection (PaginatedCollection): The collection to iterate over.
        
        Raises:
            TypeError: If the provided collection is not a PaginatedCollection instance.
        """
        if not isinstance(collection, PaginatedCollection):
            raise TypeError("PaginatedIterator expects a PaginatedCollection instance")
        self.collection = collection
        self.collection._no_iter_next = True

    def __iter__(self):
        """Iterates over pages, yielding one page at a time."""
        current_page = self.collection
        while True:
            yield current_page
            try:
                current_page = current_page.next_page(no_cache=True)
            except IndexError:
                return
