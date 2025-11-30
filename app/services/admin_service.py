"""
Admin service for dashboard, analytics, and system management.

Provides aggregated metrics, user analytics, and operational insights
for administrative dashboards.
"""

from datetime import datetime, timedelta
from typing import Any

from app.core.config import settings
from app.core.mongo import (
    applications_collection,
    failed_applications_collection,
    success_applications_collection,
    webhooks_collection,
)
from app.log.logging import logger


class AdminService:
    """Service for admin dashboard and analytics operations."""

    def __init__(self):
        self.applications = applications_collection
        self.success_apps = success_applications_collection
        self.failed_apps = failed_applications_collection
        self.webhooks = webhooks_collection

    # =========================================================================
    # Dashboard Summary
    # =========================================================================

    async def get_dashboard_summary(self) -> dict[str, Any]:
        """
        Get aggregated dashboard summary.

        Returns summary statistics for the admin dashboard including
        user counts, application metrics, and system health.
        """
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        # Get application counts
        total_pending = await self.applications.count_documents({})
        total_success = await self.success_apps.count_documents({})
        total_failed = await self.failed_apps.count_documents({})
        total_applications = total_pending + total_success + total_failed

        # Today's applications
        apps_today = await self._count_applications_since(today_start)

        # Calculate success rate
        processed = total_success + total_failed
        success_rate = (total_success / processed * 100) if processed > 0 else 0

        # Get unique users (24h and total)
        active_users_24h = await self._get_unique_users_since(now - timedelta(hours=24))
        total_users = await self._get_total_unique_users()

        # Get average processing time from recent successful apps
        avg_processing_time = await self._get_avg_processing_time()

        # Get queue depths (placeholder - would need RabbitMQ management API)
        queue_info = await self._get_queue_info()

        # Get health status
        health_status = await self._get_health_status()

        return {
            "summary": {
                "total_users": total_users,
                "active_users_24h": active_users_24h,
                "total_applications": total_applications,
                "applications_today": apps_today,
                "success_rate": round(success_rate, 1),
                "avg_processing_time_seconds": avg_processing_time,
            },
            "breakdown": {
                "pending": total_pending,
                "successful": total_success,
                "failed": total_failed,
            },
            "queues": queue_info,
            "health": health_status,
            "timestamp": now.isoformat() + "Z",
        }

    async def _count_applications_since(self, since: datetime) -> int:
        """Count applications created since a given time."""
        count = 0

        # Count from all collections
        for collection in [self.applications, self.success_apps, self.failed_apps]:
            count += await collection.count_documents({"created_at": {"$gte": since}})

        return count

    async def _get_unique_users_since(self, since: datetime) -> int:
        """Get count of unique users active since a given time."""
        users = set()

        for collection in [self.applications, self.success_apps, self.failed_apps]:
            pipeline = [
                {"$match": {"created_at": {"$gte": since}}},
                {"$group": {"_id": "$user_id"}},
            ]
            async for doc in collection.aggregate(pipeline):
                users.add(doc["_id"])

        return len(users)

    async def _get_total_unique_users(self) -> int:
        """Get total unique users across all collections."""
        users = set()

        for collection in [self.applications, self.success_apps, self.failed_apps]:
            pipeline = [{"$group": {"_id": "$user_id"}}]
            async for doc in collection.aggregate(pipeline):
                users.add(doc["_id"])

        return len(users)

    async def _get_avg_processing_time(self) -> float:
        """Get average processing time from recent successful applications."""
        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": datetime.utcnow() - timedelta(days=7)},
                    "processed_at": {"$exists": True},
                }
            },
            {
                "$project": {
                    "processing_time": {
                        "$subtract": ["$processed_at", "$created_at"]
                    }
                }
            },
            {"$group": {"_id": None, "avg_time": {"$avg": "$processing_time"}}},
        ]

        result = await self.success_apps.aggregate(pipeline).to_list(1)
        if result and result[0].get("avg_time"):
            return round(result[0]["avg_time"] / 1000, 1)  # Convert ms to seconds
        return 0.0

    async def _get_queue_info(self) -> dict[str, Any]:
        """
        Get queue information.

        Note: Full queue metrics would require RabbitMQ Management API.
        This returns placeholder/estimated values.
        """
        # Count pending applications as proxy for queue depth
        pending_count = await self.applications.count_documents({"status": "pending"})
        processing_count = await self.applications.count_documents(
            {"status": "processing"}
        )

        return {
            "processing": {
                "depth": pending_count + processing_count,
                "estimated_pending": pending_count,
                "estimated_processing": processing_count,
            },
            "dlq": {
                "depth": 0,  # Would need RabbitMQ API
                "oldest_message_age_hours": None,
            },
        }

    async def _get_health_status(self) -> dict[str, str]:
        """Get basic health status of dependencies."""
        from app.core.database import check_mongodb_health
        from app.core.rabbitmq import check_rabbitmq_health

        health = {}

        try:
            mongodb_ok = await check_mongodb_health()
            health["mongodb"] = "healthy" if mongodb_ok else "unhealthy"
        except Exception:
            health["mongodb"] = "unhealthy"

        try:
            rabbitmq_ok = await check_rabbitmq_health()
            health["rabbitmq"] = "healthy" if rabbitmq_ok else "unhealthy"
        except Exception:
            health["rabbitmq"] = "unhealthy"

        # Redis health
        try:
            from app.core.redis_cache import redis_cache

            if redis_cache:
                health["redis"] = "healthy"
            else:
                health["redis"] = "unavailable"
        except Exception:
            health["redis"] = "unavailable"

        return health

    # =========================================================================
    # Analytics
    # =========================================================================

    async def get_application_analytics(
        self,
        period: str = "day",
        group_by: str = "status",
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Get application analytics with time-series data.

        Args:
            period: Aggregation period (hour, day, week, month)
            group_by: Grouping field (status, portal, user)
            from_date: Start date for query
            to_date: End date for query
        """
        now = datetime.utcnow()

        # Default date range based on period
        if to_date is None:
            to_date = now
        if from_date is None:
            period_days = {"hour": 1, "day": 7, "week": 30, "month": 90}
            from_date = now - timedelta(days=period_days.get(period, 7))

        # Get time-series data
        time_series = await self._get_time_series_data(from_date, to_date, period)

        # Get totals by status
        totals = await self._get_totals_in_range(from_date, to_date)

        # Get breakdown by group_by field
        breakdown = await self._get_breakdown_by_field(from_date, to_date, group_by)

        return {
            "period": period,
            "from": from_date.isoformat() + "Z",
            "to": to_date.isoformat() + "Z",
            "data": time_series,
            "totals": totals,
            "breakdown": breakdown,
        }

    async def _get_time_series_data(
        self, from_date: datetime, to_date: datetime, period: str
    ) -> list[dict]:
        """Generate time-series data for applications."""
        # Determine date format for grouping
        date_formats = {
            "hour": "%Y-%m-%dT%H:00:00Z",
            "day": "%Y-%m-%dT00:00:00Z",
            "week": "%Y-W%V",
            "month": "%Y-%m-01T00:00:00Z",
        }

        date_format = date_formats.get(period, "%Y-%m-%dT00:00:00Z")

        # Aggregate from success and failed collections
        data = {}

        for collection, status in [
            (self.success_apps, "success"),
            (self.failed_apps, "failed"),
        ]:
            pipeline = [
                {"$match": {"created_at": {"$gte": from_date, "$lte": to_date}}},
                {
                    "$group": {
                        "_id": {"$dateToString": {"format": date_format, "date": "$created_at"}},
                        "count": {"$sum": 1},
                    }
                },
                {"$sort": {"_id": 1}},
            ]

            async for doc in collection.aggregate(pipeline):
                timestamp = doc["_id"]
                if timestamp not in data:
                    data[timestamp] = {"timestamp": timestamp, "success": 0, "failed": 0}
                data[timestamp][status] = doc["count"]

        # Add pending/processing from applications collection
        pipeline = [
            {"$match": {"created_at": {"$gte": from_date, "$lte": to_date}}},
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": date_format, "date": "$created_at"}},
                        "status": "$status",
                    },
                    "count": {"$sum": 1},
                }
            },
        ]

        async for doc in self.applications.aggregate(pipeline):
            timestamp = doc["_id"]["date"]
            status = doc["_id"]["status"]
            if timestamp not in data:
                data[timestamp] = {"timestamp": timestamp, "success": 0, "failed": 0}
            if status in ["pending", "processing"]:
                data[timestamp][status] = doc["count"]

        return sorted(data.values(), key=lambda x: x["timestamp"])

    async def _get_totals_in_range(
        self, from_date: datetime, to_date: datetime
    ) -> dict[str, Any]:
        """Get totals for applications in date range."""
        query = {"created_at": {"$gte": from_date, "$lte": to_date}}

        success_count = await self.success_apps.count_documents(query)
        failed_count = await self.failed_apps.count_documents(query)
        pending_count = await self.applications.count_documents(query)

        total = success_count + failed_count + pending_count
        success_rate = (success_count / (success_count + failed_count) * 100) if (success_count + failed_count) > 0 else 0

        return {
            "total": total,
            "success": success_count,
            "failed": failed_count,
            "pending": pending_count,
            "success_rate": round(success_rate, 1),
        }

    async def _get_breakdown_by_field(
        self, from_date: datetime, to_date: datetime, field: str
    ) -> list[dict]:
        """Get application breakdown by a specific field."""
        if field not in ["status", "portal", "user_id"]:
            field = "status"

        breakdown = {}

        for collection in [self.success_apps, self.failed_apps]:
            pipeline = [
                {"$match": {"created_at": {"$gte": from_date, "$lte": to_date}}},
                {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 20},
            ]

            async for doc in collection.aggregate(pipeline):
                key = str(doc["_id"]) if doc["_id"] else "unknown"
                if key not in breakdown:
                    breakdown[key] = 0
                breakdown[key] += doc["count"]

        return [{"value": k, "count": v} for k, v in sorted(breakdown.items(), key=lambda x: -x[1])]

    async def get_user_analytics(
        self, from_date: datetime | None = None, to_date: datetime | None = None
    ) -> dict[str, Any]:
        """Get user-related analytics."""
        now = datetime.utcnow()
        if to_date is None:
            to_date = now
        if from_date is None:
            from_date = now - timedelta(days=30)

        # Top users by application count
        top_users = await self._get_top_users(from_date, to_date, limit=10)

        # User activity over time
        active_users_today = await self._get_unique_users_since(
            now.replace(hour=0, minute=0, second=0, microsecond=0)
        )
        active_users_week = await self._get_unique_users_since(now - timedelta(days=7))
        active_users_month = await self._get_unique_users_since(now - timedelta(days=30))

        return {
            "top_users": top_users,
            "activity": {
                "active_today": active_users_today,
                "active_week": active_users_week,
                "active_month": active_users_month,
            },
            "period": {
                "from": from_date.isoformat() + "Z",
                "to": to_date.isoformat() + "Z",
            },
        }

    async def _get_top_users(
        self, from_date: datetime, to_date: datetime, limit: int = 10
    ) -> list[dict]:
        """Get top users by application count."""
        user_stats = {}

        for collection, status in [
            (self.success_apps, "success"),
            (self.failed_apps, "failed"),
        ]:
            pipeline = [
                {"$match": {"created_at": {"$gte": from_date, "$lte": to_date}}},
                {
                    "$group": {
                        "_id": "$user_id",
                        "count": {"$sum": 1},
                        "last_active": {"$max": "$created_at"},
                    }
                },
            ]

            async for doc in collection.aggregate(pipeline):
                user_id = str(doc["_id"])
                if user_id not in user_stats:
                    user_stats[user_id] = {
                        "user_id": user_id,
                        "total": 0,
                        "success": 0,
                        "failed": 0,
                        "last_active": None,
                    }
                user_stats[user_id]["total"] += doc["count"]
                user_stats[user_id][status] = doc["count"]
                if doc["last_active"]:
                    if user_stats[user_id]["last_active"] is None or doc["last_active"] > user_stats[user_id]["last_active"]:
                        user_stats[user_id]["last_active"] = doc["last_active"]

        # Calculate success rate and sort
        result = []
        for user in user_stats.values():
            total_processed = user["success"] + user["failed"]
            user["success_rate"] = (
                round(user["success"] / total_processed * 100, 1) if total_processed > 0 else 0
            )
            if user["last_active"]:
                user["last_active"] = user["last_active"].isoformat() + "Z"
            result.append(user)

        return sorted(result, key=lambda x: -x["total"])[:limit]

    async def get_error_analytics(
        self, from_date: datetime | None = None, to_date: datetime | None = None
    ) -> dict[str, Any]:
        """Get error breakdown and trends."""
        now = datetime.utcnow()
        if to_date is None:
            to_date = now
        if from_date is None:
            from_date = now - timedelta(days=7)

        # Error breakdown by reason
        error_breakdown = await self._get_error_breakdown(from_date, to_date)

        # Error rate trend (hourly for last 24h)
        error_trend = await self._get_error_trend(now - timedelta(hours=24), now)

        # Total error count
        total_errors = await self.failed_apps.count_documents(
            {"created_at": {"$gte": from_date, "$lte": to_date}}
        )

        return {
            "total_errors": total_errors,
            "error_breakdown": error_breakdown,
            "error_rate_trend": error_trend,
            "period": {
                "from": from_date.isoformat() + "Z",
                "to": to_date.isoformat() + "Z",
            },
        }

    async def _get_error_breakdown(
        self, from_date: datetime, to_date: datetime
    ) -> list[dict]:
        """Get breakdown of errors by reason."""
        pipeline = [
            {"$match": {"created_at": {"$gte": from_date, "$lte": to_date}}},
            {
                "$group": {
                    "_id": "$error_reason",
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]

        result = []
        total = 0
        async for doc in self.failed_apps.aggregate(pipeline):
            error_type = doc["_id"] or "unknown"
            count = doc["count"]
            total += count
            result.append({"error_type": error_type, "count": count})

        # Add percentages
        for item in result:
            item["percentage"] = round(item["count"] / total * 100, 1) if total > 0 else 0

        return result

    async def _get_error_trend(
        self, from_date: datetime, to_date: datetime
    ) -> list[dict]:
        """Get hourly error rate trend."""
        pipeline = [
            {"$match": {"created_at": {"$gte": from_date, "$lte": to_date}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%dT%H:00:00Z",
                            "date": "$created_at",
                        }
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]

        result = []
        async for doc in self.failed_apps.aggregate(pipeline):
            result.append({"hour": doc["_id"], "errors": doc["count"]})

        return result

    # =========================================================================
    # User Management
    # =========================================================================

    async def list_users(
        self,
        search: str | None = None,
        sort_by: str = "total_applications",
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List users with their statistics.

        Args:
            search: Search by user ID
            sort_by: Sort field (total_applications, last_active)
            limit: Number of results
            offset: Pagination offset
        """
        # Get all unique users with their stats
        user_stats = await self._get_all_user_stats()

        # Filter by search
        if search:
            user_stats = [u for u in user_stats if search.lower() in str(u["user_id"]).lower()]

        # Sort
        if sort_by == "last_active":
            user_stats.sort(key=lambda x: x.get("last_active") or "", reverse=True)
        else:
            user_stats.sort(key=lambda x: -x.get("total_applications", 0))

        # Paginate
        total = len(user_stats)
        users = user_stats[offset : offset + limit]

        return {
            "users": users,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            },
        }

    async def _get_all_user_stats(self) -> list[dict]:
        """Get statistics for all users."""
        user_stats = {}

        for collection, status in [
            (self.applications, "pending"),
            (self.success_apps, "success"),
            (self.failed_apps, "failed"),
        ]:
            pipeline = [
                {
                    "$group": {
                        "_id": "$user_id",
                        "count": {"$sum": 1},
                        "last_active": {"$max": "$created_at"},
                    }
                }
            ]

            async for doc in collection.aggregate(pipeline):
                user_id = str(doc["_id"])
                if user_id not in user_stats:
                    user_stats[user_id] = {
                        "user_id": user_id,
                        "total_applications": 0,
                        "pending": 0,
                        "successful": 0,
                        "failed": 0,
                        "last_active": None,
                    }
                user_stats[user_id]["total_applications"] += doc["count"]

                if status == "pending":
                    user_stats[user_id]["pending"] = doc["count"]
                elif status == "success":
                    user_stats[user_id]["successful"] = doc["count"]
                elif status == "failed":
                    user_stats[user_id]["failed"] = doc["count"]

                if doc["last_active"]:
                    current = user_stats[user_id]["last_active"]
                    if current is None or doc["last_active"] > current:
                        user_stats[user_id]["last_active"] = doc["last_active"]

        # Format and calculate success rate
        result = []
        for user in user_stats.values():
            processed = user["successful"] + user["failed"]
            user["success_rate"] = (
                round(user["successful"] / processed * 100, 1) if processed > 0 else 0
            )
            if user["last_active"]:
                user["last_active"] = user["last_active"].isoformat() + "Z"
            result.append(user)

        return result

    async def get_user_details(self, user_id: str) -> dict[str, Any] | None:
        """Get detailed information about a specific user."""
        # Get statistics
        pending = await self.applications.count_documents({"user_id": int(user_id)})
        success = await self.success_apps.count_documents({"user_id": int(user_id)})
        failed = await self.failed_apps.count_documents({"user_id": int(user_id)})

        if pending == 0 and success == 0 and failed == 0:
            return None

        total = pending + success + failed
        success_rate = round(success / (success + failed) * 100, 1) if (success + failed) > 0 else 0

        # Get recent applications
        recent_apps = []
        cursor = self.success_apps.find(
            {"user_id": int(user_id)}
        ).sort("created_at", -1).limit(5)

        async for doc in cursor:
            recent_apps.append({
                "id": str(doc.get("_id")),
                "status": "success",
                "created_at": doc.get("created_at").isoformat() + "Z" if doc.get("created_at") else None,
                "portal": doc.get("portal"),
            })

        # Get webhooks count
        webhooks_count = await self.webhooks.count_documents({"user_id": user_id})

        return {
            "user_id": user_id,
            "statistics": {
                "total_applications": total,
                "pending": pending,
                "successful": success,
                "failed": failed,
                "success_rate": success_rate,
            },
            "webhooks_count": webhooks_count,
            "recent_applications": recent_apps,
        }


# Singleton instance
admin_service = AdminService()
