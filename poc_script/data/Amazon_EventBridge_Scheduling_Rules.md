
# Using Cron and Rate Expressions to Schedule Rules in Amazon EventBridge

When you create a scheduled rule in EventBridge, you can specify a schedule pattern that determines when EventBridge runs the rule:
- **Cron Expression**: Use this to run the rule at specific times and dates.
- **Rate Expression**: Use this to run the rule at regular intervals.


# Amazon EventBridge Scheduler

The following topic describes the different schedule types that Amazon EventBridge Scheduler supports, as well as how EventBridge Scheduler handles daylight savings time and scheduling in different time zones. You can choose from three schedule types when configuring your schedule:
- **Rate-based schedules**
- **Cron-based schedules**
- **One-time schedules**

Both rate-based and cron-based schedules are recurring schedules. You configure each recurring schedule type using a schedule expression for the type of schedule you want to configure, and specify a time zone in which EventBridge Scheduler evaluates the expression.

A one-time schedule is a schedule that invokes a target only once. You configure a one-time schedule by specifying the time, date, and time zone in which EventBridge Scheduler evaluates the schedule.

> **Note**: All schedule types on EventBridge Scheduler invoke their targets with 60-second precision. This means that if you set your schedule to run at 1:00, it will invoke the target API between 1:00:00 and 1:00:59, assuming that a flexible time window is not set.

Use the following sections to learn about configuring schedule expressions for each recurring schedule type and how to set up a one-time schedule on EventBridge Scheduler.

### Topics
- Rate-based schedules
- Cron-based schedules
- One-time schedules
- Time zones on EventBridge Scheduler
- Daylight savings time on EventBridge Scheduler

## Rate-based Schedules

A rate-based schedule starts after the start date you specify for your schedule and runs at a regular rate that you define until the schedule's end date. You can set up most common recurrent scheduling use cases using a rate-based schedule. For example, if you want a schedule that invokes its target every 15 minutes, once every two hours, or once every five days, you can use a rate-based schedule to achieve this. You configure a rate-based schedule using a rate expression.

With rate-based schedules, you use the `StartDate` property to set the first occurrence of the schedule. If you do not provide a `StartDate` for a rate-based schedule, your schedule starts invoking the target immediately.

**Syntax**
```
rate(value unit)
```
- **value**: A positive number.
- **unit**: The unit of time you want your schedule to invoke its target.

#### Valid Inputs
- `minutes` | `hours` | `days`

### Example
The following example shows how to use rate expressions with the AWS CLI `create-schedule` command to configure a rate-based schedule. This example creates a schedule that runs every five minutes and delivers a message to an Amazon SQS queue using the templated `SqsParameters` target type.

Because this example does not set a value for the `--start-date` parameter, the schedule starts invoking its target immediately after you create and activate it.


## Cron Expressions

Cron expressions have six required fields, separated by white space:

| Field         | Range                       | Wildcards       |
|---------------|-----------------------------|-----------------|
| Minutes       | 0-59                        | `, - * /`       |
| Hours         | 0-23                        | `, - * /`       |
| Day-of-month  | 1-31                        | `, - * ? / L W` |
| Month         | 1-12 or JAN-DEC             | `, - * /`       |
| Day-of-week   | 1-7 or SUN-SAT              | `, - * ? L #`   |
| Year          | 1970-2199                   | `, - * /`       |

### Wildcards
- **Comma (,)**: Includes additional values. Example: `JAN,FEB,MAR` in the Month field includes January, February, and March.
- **Dash (-)**: Specifies ranges. Example: `1-15` in the Day field includes days 1 through 15 of the month.
- **Asterisk (*)**: Includes all values in the field. Example: `*` in the Hours field includes every hour.
  - Note: You can't use `*` in both the Day-of-month and Day-of-week fields. If one uses `*`, the other must use `?`.
- **Slash (/)**: Specifies increments. Example: `1/10` in the Minutes field specifies every tenth minute, starting at minute 1.
- **Question Mark (?)**: Specifies "any". Example: `?` in the Day-of-week field when a specific day of the month is set.
- **L**: Specifies the last day of the month or week.
- **W**: Specifies a weekday closest to a specific day. Example: `3W` specifies the weekday closest to the third day of the month.
- **#**: Specifies a specific occurrence of a weekday within a month. Example: `3#2` means the second Tuesday of the month.

#### Note
If you use a `#` character, you can define only one expression in the Day-of-week field. Example: `"3#1,6#3"` is invalid.

### Limitations
- You can't specify both Day-of-month and Day-of-week fields in the same expression. If one is used with a value or `*`, the other must use `?`.
- Cron expressions faster than one minute are not supported.

## Rate Expressions

A rate expression starts when you create the scheduled event rule, and it then runs on a defined schedule.

### Syntax
```
rate(value unit)
```
- **value**: A positive number.
- **unit**: The unit of time, which varies for values. `minute` for 1 and `minutes` for more than 1.

#### Valid Values
- `minute | minutes | hour | hours | day | days`

### Limitations
- If `value` is equal to 1, the unit must be singular. Example: `rate(1 hour)`.
- If `value` is greater than 1, the unit must be plural. Example: `rate(5 hours)`.

### Examples
The following examples show rate expressions using the AWS CLI `put-rule` command:
- `rate(1 minute)`: Triggers the rule every minute.
- `rate(5 minutes)`: Triggers the rule every five minutes.
- `rate(1 hour)`: Triggers the rule once per hour.
- `rate(1 day)`: Triggers the rule once per day.

## Example Cron Strings

You can use the following sample cron strings when creating a rule with a schedule.

| Minutes | Hours | Day of Month | Month | Day of Week | Year | Meaning |
|---------|-------|--------------|-------|-------------|------|---------|
| 0       | 10    | *            | *     | ?           | *    | Run at 10:00 am (UTC+0) every day |
| 15      | 12    | *            | *     | ?           | *    | Run at 12:15 pm (UTC+0) every day |
| 0       | 18    | ?            | *     | MON-FRI     | *    | Run at 6:00 pm (UTC+0) every Monday through Friday |
| 0       | 8     | 1            | *     | ?           | *    | Run at 8:00 am (UTC+0) every 1st day of the month |
| 0/15    | *     | *            | *     | ?           | *    | Run every 15 minutes |
| 0/10    | *     | ?            | *     | MON-FRI     | *    | Run every 10 minutes Monday through Friday |
| 0/5     | 8-17  | ?            | *     | MON-FRI     | *    | Run every 5 minutes Monday through Friday between 8:00 am and 5:55 pm (UTC+0) |
| 0/30    | 20-2  | ?            | *     | MON-FRI     | *    | Run every 30 minutes Monday through Friday between 10:00 pm on the starting day to 2:00 am on the following day (UTC) |

Additional Example: Run from 12:00 am to 2:00 am on Monday morning (UTC).

## One-Time Schedules

A one-time schedule will invoke a target only once at the date and time that you specify using a valid date and timestamp. EventBridge Scheduler supports scheduling in Universal Coordinated Time (UTC), or in the time zone that you specify when you create your schedule.

> **Note**: A one-time schedule still counts against your account quota after it has completed running and invoking its target. We recommend deleting your one-time schedules after they've completed running.

### Configuring a One-Time Schedule

You configure a one-time schedule using an `at` expression. An `at` expression consists of the date and time at which you want EventBridge Scheduler to invoke your schedule:

**Syntax**
```
at(yyyy-mm-ddThh:mm:ss)
```
When you configure a one-time schedule, EventBridge Scheduler ignores the `StartDate` and `EndDate` you specify for the schedule.

### Example
The following example shows how to use `at` expressions with the AWS CLI `create-schedule` command to configure a one-time schedule. This example creates a schedule that runs once at 1pm UTC-8 on November 20, 2022, and delivers a message to an Amazon SQS queue using the templated `SqsParameters` target type:

```sh
$ aws scheduler create-schedule --schedule-expression "at(2022-11-20T13:00:00)" --name schedule-name \
    --target '{"RoleArn": "role-arn", "Arn": "QUEUE_ARN", "Input": "TEST_PAYLOAD" }' \
    --schedule-expression-timezone "America/Los_Angeles" \
    --flexible-time-window '{ "Mode": "OFF"}'
```

## Time Zones on EventBridge Scheduler

EventBridge Scheduler supports configuring both cron-based and one-time schedules in any time zone that you specify. It uses the Time Zone Database maintained by the Internet Assigned Numbers Authority (IANA).

Using the AWS CLI, you can set the time zone for schedule evaluation using the `--schedule-expression-timezone` parameter. For example, the following command creates a cron-based schedule that invokes a templated Amazon SQS `SendMessage` target in the `America/New_York` time zone every day at 8:30 a.m.:

```sh
$ aws scheduler create-schedule --schedule-expression "cron(30 8 * * ? *)" --name schedule-in-est \
    --target '{"RoleArn": "role-arn", "Arn": "QUEUE_ARN", "Input": "This schedule runs in the America/New_York time zone." }' \
    --schedule-expression-timezone "America/New_York" \
    --flexible-time-window '{ "Mode": "OFF"}'
```

## Daylight Savings Time on EventBridge Scheduler

EventBridge Scheduler automatically adjusts schedules for daylight saving time. 
- **Spring-forward**: If time shifts forward in Spring (e.g., from 1:59 a.m. to 3:00 a.m.), and a cron expression falls on the non-existent time, the invocation is skipped for that day.
- **Fall-back**: If time shifts backward in Fall (e.g., from 2:59 a.m. to 2:00 a.m.), the schedule runs only once and does not repeat at the time after the shift.

EventBridge Scheduler adjusts the schedule based on the time zone you specify at creation. For example, if you configure a schedule in `America/New_York`, it adjusts with that time zone’s daylight savings, while a schedule in `America/Los_Angeles` adjusts later when time changes on the west coast.

### Note on UTC and Non-DST Zones
Some time zones do not observe daylight saving time. In such cases, EventBridge Scheduler does not adjust the schedule for daylight savings. Daylight-saving adjustments do not apply to schedules configured in Universal Coordinated Time (UTC).

### Example Scenario
Consider a schedule created with the following cron expression in `America/Los_Angeles`: `cron(30 2 * * ? *)`. This schedule runs every day at 2:30 a.m. in the specified time zone.

- **Spring-forward**: When time shifts from 1:59 a.m. to 3:00 a.m., the invocation is skipped on that day, resuming normally the next day.
- **Fall-back**: When time shifts from 2:59 a.m. to 2:00 a.m., the schedule runs at 2:30 a.m. before the time shift, but does not repeat the invocation after the time shift.

For rate-based schedules with days as the unit, such as `rate(1 day)`, EventBridge Scheduler interprets days as 24-hour durations on the clock.

### Note on DAYS

Day-of-week can be represented by numeric values 1-7 (1 - Sunday, 2 - Monday, 3 - Tuesday, 4-Wednesday, 5-Thursday, 6-Friday 7 for Saturday) or strings (SUN-SAT).


