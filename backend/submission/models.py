from django.db import models

from utils.constants import ContestStatus
from django.db.models import JSONField
from problem.models import Problem
from contest.models import Contest

from utils.shortcuts import rand_str

from assignment.models import Assignment


class JudgeStatus:
    COMPILE_ERROR = -2
    WRONG_ANSWER = -1
    ACCEPTED = 0
    CPU_TIME_LIMIT_EXCEEDED = 1
    REAL_TIME_LIMIT_EXCEEDED = 2
    MEMORY_LIMIT_EXCEEDED = 3
    RUNTIME_ERROR = 4
    SYSTEM_ERROR = 5
    PENDING = 6
    JUDGING = 7
    PARTIALLY_ACCEPTED = 8


class Submission(models.Model):
    id = models.TextField(default=rand_str, primary_key=True, db_index=True)
    contest = models.ForeignKey(Contest, null=True, on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, null=True, on_delete=models.CASCADE, related_name="submissions")
    create_time = models.DateTimeField(auto_now_add=True)
    user_id = models.IntegerField(db_index=True)
    username = models.TextField()
    code = models.TextField()
    result = models.IntegerField(db_index=True, default=JudgeStatus.PENDING)
    # Judgment details returned from JudgeServer
    info = JSONField(default=dict)
    language = models.TextField()
    shared = models.BooleanField(default=False)
    # Store the time and memory value of the submission to facilitate the submission list display
    # {time_cost: "", memory_cost: "", err_info: "", score: 0}
    statistic_info = JSONField(default=dict)
    ip = models.TextField(null=True)

    def check_user_permission(self, user, check_share=True):
        if self.user_id == user.id or user.is_super_admin() or user.can_mgmt_all_problem() or self.problem.created_by_id == user.id:
            return True

        if check_share:
            if self.contest and self.contest.status != ContestStatus.CONTEST_ENDED:
                return False
            if self.problem.share_submission or self.shared:
                return True
        return False

    class Meta:
        db_table = "submission"
        ordering = ("-create_time",)

    def __str__(self):
        return self.id
