from utils.constants import ContestRuleType  # noqa
from django.db import models
from django.utils.timezone import now
from django.db.models import JSONField

from utils.constants import ContestStatus, ContestType
from account.models import User
from group.models import Group
from utils.models import RichTextField


class Contest(models.Model):
    title = models.TextField()
    description = RichTextField()
    requirements = JSONField(default=list)
    constraints = JSONField(default=list)
    allowed_groups = models.ManyToManyField(Group, blank=True)
    scoring = models.TextField(default="ACM-ICPC style")
    # show real time rank or cached rank
    real_time_rank = models.BooleanField()
    password = models.TextField(null=True)
    # enum of ContestRuleType
    rule_type = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    create_time = models.DateTimeField(auto_now_add=True)
    last_update_time = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    # If it is visible, false is equivalent to delete
    visible = models.BooleanField(default=True)
    allowed_ip_ranges = JSONField(default=list)
    bank_filter = JSONField(default=None, null=True)
    rank_penalty_visible = models.BooleanField(default=True)

    @property
    def is_bank(self):
        return True if self.bank_filter else False

    @property
    def status(self):
        if self.start_time > now():
            # NOT_START return 1
            return ContestStatus.CONTEST_NOT_START
        elif self.end_time < now():
            # ENDED return -1
            return ContestStatus.CONTEST_ENDED
        else:
            # UNDERWAY return 0
            return ContestStatus.CONTEST_UNDERWAY

    @property
    def contest_type(self):
        if self.password:
            return ContestType.PASSWORD_PROTECTED_CONTEST
        return ContestType.PUBLIC_CONTEST

    # The permission to view some statistics of the problem, such as submission_number, accepted_number, etc.
    def problem_details_permission(self, user):
        return self.rule_type == ContestRuleType.ACM or \
            self.status == ContestStatus.CONTEST_ENDED or \
            user.is_authenticated and user.is_contest_admin(self) or \
            self.real_time_rank

    class Meta:
        db_table = "contest"
        ordering = ("-start_time",)


class ContestPrize(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="prizes")
    color = models.TextField()
    name = models.TextField()
    reward = models.TextField()


class AbstractContestRank(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    submission_number = models.IntegerField(default=0)
    prize = models.ForeignKey(ContestPrize, on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        abstract = True


class ACMContestRank(AbstractContestRank):
    accepted_number = models.IntegerField(default=0)
    # total_time is only for ACM contest, total_time =  ac time + none-ac times * 20 * 60
    total_time = models.IntegerField(default=0)
    # {"23": {"is_ac": True, "ac_time": 8999, "problem_submission": 2, "penalty": 496}}
    total_penalty = models.IntegerField(default=0)
    # key is problem id
    submission_info = JSONField(default=dict)

    class Meta:
        db_table = "acm_contest_rank"
        unique_together = (("user", "contest"),)


class OIContestRank(AbstractContestRank):
    total_score = models.IntegerField(default=0)
    # {"23": 333}
    # key is problem id, value is current score
    submission_info = JSONField(default=dict)

    class Meta:
        db_table = "oi_contest_rank"
        unique_together = (("user", "contest"),)


class ProblemBank(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    problem_list = models.TextField(null=True)

    class Meta:
        db_table = "problem_bank"
        unique_together = (("user", "contest"),)


class ContestAnnouncement(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    problem = models.ForeignKey("problem.Problem", on_delete=models.CASCADE, default=None)
    title = models.TextField()
    content = RichTextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    visible = models.BooleanField(default=True)
    create_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "contest_announcement"
        ordering = ("-create_time",)
