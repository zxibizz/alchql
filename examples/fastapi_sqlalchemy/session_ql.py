from contextlib import asynccontextmanager, contextmanager
from inspect import isawaitable
from typing import Any, Dict

from graphql import graphql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from starlette.background import BackgroundTasks
from starlette.requests import HTTPConnection, Request
from starlette.responses import JSONResponse
from starlette_graphene3 import GraphQLApp, _get_operation_from_request


class SessionQLApp(GraphQLApp):
    def __init__(self, db_url, *args, **kwargs):
        engine = create_async_engine(db_url, convert_unicode=True, echo=True)
        self.db_session = scoped_session(
            sessionmaker(
                autocommit=False, autoflush=False, bind=engine, class_=AsyncSession
            )
        )

        super().__init__(*args, **kwargs)

    async def _handle_http_request(self, request: Request) -> JSONResponse:
        try:
            operations = await _get_operation_from_request(request)
        except ValueError as e:
            return JSONResponse({"errors": [e.args[0]]}, status_code=400)

        if isinstance(operations, list):
            return JSONResponse(
                {"errors": ["This server does not support batching"]}, status_code=400
            )
        else:
            operation = operations

        query = operation["query"]
        variable_values = operation.get("variables")
        operation_name = operation.get("operationName")

        async with self._get_context_value(request) as context_value:
            result = await graphql(
                self.schema.graphql_schema,
                source=query,
                context_value=context_value,
                root_value=self.root_value,
                middleware=self.middleware,
                variable_values=variable_values,
                operation_name=operation_name,
                execution_context_class=self.execution_context_class,
            )
            background = context_value.get("background")

        response: Dict[str, Any] = {"data": result.data}
        if result.errors:
            for error in result.errors:
                if error.original_error:
                    self.logger.error(
                        "An exception occurred in resolvers",
                        exc_info=error.original_error,
                    )
            response["errors"] = [
                self.error_formatter(error) for error in result.errors
            ]

        return JSONResponse(
            response,
            status_code=200,
            background=background,
        )

    @asynccontextmanager
    async def _get_context_value(self, request: HTTPConnection) -> Any:
        # engine = create_async_engine(self.db_url, echo=True)

        print("SESSION OPENED")
        # with Transaction(self.db_url, echo=True) as t:
        async with self.db_session() as session:
            async with session.begin():
                if callable(self.context_value):
                    context = self.context_value(
                        request=request,
                        background=BackgroundTasks(),
                        session=session,
                    )
                    if isawaitable(context):
                        context = await context
                    yield context
                else:
                    yield self.context_value or {
                        "request": request,
                        "background": BackgroundTasks(),
                        "session": session,
                    }
        print("SESSION CLOSED")