"""
PID Conversion report

The goal is to generate a mapping of a patient's study IDs and secondary IDs.

Patient IDs are idendification numbers assigned globally by the organization.
(e.g. OUR Numbers)

Study IDs are identification numbers assigned only within a study scope.
(e.g. AEH Early Test)

Secondary IDs are identication numbers assigned in external  systems.
(e.g. Medical Record Numbers, AIDRP number)

Formerly: avrcdataexport/sql/additional/OurEarlyTest.sql
"""

from pyramid.decorator import reify
from sqlalchemy import literal_column
from sqlalchemy.orm import aliased

from .. import _, models
from ..utils.sql import group_concat
from .plan import ExportPlan
from .codebook import row, types


class PidPlan(ExportPlan):

    name = 'pid'

    title = _(u'Patient Identifiers')

    @reify
    def reftypes(self):
        return list(
            self.dbsession.query(models.ReferenceType)
            .order_by(models.ReferenceType.name))

    def codebook(self):
        name = self.name
        knowns = [
            row('id', name, types.NUMBER, decimal_places=0, is_required=True,
                is_system=True),
            row('pid', name, types.STRING, is_required=True, is_system=True),
            row('site', name, types.STRING, is_required=True, is_system=True),
            row('early_id', name, types.STRING, is_system=True),
            row('created_at', self.name, types.DATE,
                is_required=True, is_system=True),
            row('created_by', self.name, types.STRING,
                is_required=True, is_system=True),
            row('modified_at', self.name, types.DATE,
                is_required=True, is_system=True),
            row('modified_by', self.name, types.STRING, is_required=True,
                is_system=True)
        ]

        for known in knowns:
            yield known

        for reftype in self.reftypes:
            yield row(reftype.name, name, types.STRING,
                      is_system=True, is_collection=True)

    def data(self,
             use_choice_labels=False,
             expand_collections=False,
             ignore_private=True):
        session = self.dbsession
        query = (
            session.query(
                models.Patient.id.label('id'),
                models.Site.name.label('site'),
                models.Patient.pid.label('pid'))
            .join(models.Site))

        # BBB 2014-02-20 (Marco): AEH needs Early Test
        EarlyTest = aliased(models.Enrollment)
        subquery = (
            session.query(EarlyTest.patient_id, EarlyTest.reference_number)
            .filter(EarlyTest.study.has(
                models.Study.code.in_([literal_column("'ET'"),
                                       literal_column("'LTW'"),
                                       literal_column("'CVCT'")])))
            .subquery())
        query = (
            query
            .outerjoin(subquery, subquery.c.patient_id == models.Patient.id)
            .add_column(subquery.c.reference_number.label('early_id')))

        # Add every known reference number
        for reftype in self.reftypes:
            query = query.add_column(
                session.query(
                    group_concat(
                        models.PatientReference.reference_number, ';'))
                .filter(
                    models.PatientReference.patient_id == models.Patient.id)
                .filter(
                    models.PatientReference.reference_type_id == reftype.id)
                .group_by(models.PatientReference.patient_id)
                .correlate(models.Patient)
                .as_scalar()
                .label(reftype.name))

        query = (
            query
            .add_columns(
                models.Patient.created_at,
                models.Patient.created_by,
                models.Patient.modified_at,
                models.Patient.modified_by
            )
            .order_by(models.Patient.id))

        return query
