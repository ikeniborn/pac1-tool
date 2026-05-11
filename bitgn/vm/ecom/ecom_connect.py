from bitgn._connect import ConnectClient
from bitgn.vm.ecom.ecom_pb2 import (
    ContextRequest, ContextResponse,
    ReadRequest, ReadResponse,
    ListRequest, ListResponse,
    TreeRequest, TreeResponse,
    FindRequest, FindResponse,
    SearchRequest, SearchResponse,
    ExecRequest, ExecResponse,
    WriteRequest, WriteResponse,
    DeleteRequest, DeleteResponse,
    StatRequest, StatResponse,
    AnswerRequest, AnswerResponse,
)

_SERVICE = "bitgn.vm.ecom.EcomRuntime"


class EcomRuntimeClientSync:
    def __init__(self, base_url: str):
        self._c = ConnectClient(base_url)

    def context(self, req: ContextRequest) -> ContextResponse:
        return self._c.call(_SERVICE, "Context", req, ContextResponse)

    def read(self, req: ReadRequest) -> ReadResponse:
        return self._c.call(_SERVICE, "Read", req, ReadResponse)

    def list(self, req: ListRequest) -> ListResponse:
        return self._c.call(_SERVICE, "List", req, ListResponse)

    def tree(self, req: TreeRequest) -> TreeResponse:
        return self._c.call(_SERVICE, "Tree", req, TreeResponse)

    def find(self, req: FindRequest) -> FindResponse:
        return self._c.call(_SERVICE, "Find", req, FindResponse)

    def search(self, req: SearchRequest) -> SearchResponse:
        return self._c.call(_SERVICE, "Search", req, SearchResponse)

    def exec(self, req: ExecRequest) -> ExecResponse:
        return self._c.call(_SERVICE, "Exec", req, ExecResponse)

    def write(self, req: WriteRequest) -> WriteResponse:
        return self._c.call(_SERVICE, "Write", req, WriteResponse)

    def delete(self, req: DeleteRequest) -> DeleteResponse:
        return self._c.call(_SERVICE, "Delete", req, DeleteResponse)

    def stat(self, req: StatRequest) -> StatResponse:
        return self._c.call(_SERVICE, "Stat", req, StatResponse)

    def answer(self, req: AnswerRequest) -> AnswerResponse:
        return self._c.call(_SERVICE, "Answer", req, AnswerResponse)
