
# Introduction
cron is a UNIX tool that has been around for a long time, so its scheduling capabilities are powerful and proven. The CronTrigger class is based on the scheduling capabilities of cron.

CronTrigger uses “cron expressions”, which are able to create firing schedules such as: “At 8:00am every Monday through Friday” or “At 1:30am every last Friday of the month”.

Cron expressions are powerful, but can be pretty confusing. This tutorial aims to take some of the mystery out of creating a cron expression, giving users a resource which they can visit before having to ask in a forum or mailing list.

## Format
A cron expression is a string comprised of 6 or 7 fields separated by white space. Fields can contain any of the allowed values, along with various combinations of the allowed special characters for that field. The fields are as follows:

| Field Name    | Mandatory | Allowed Values          | Allowed Special Characters |
|---------------|-----------|-------------------------|----------------------------|
| Seconds       | YES       | 0-59                    | , - * /                    |
| Minutes       | YES       | 0-59                    | , - * /                    |
| Hours         | YES       | 0-23                    | , - * /                    |
| Day of month  | YES       | 1-31                    | , - * ? / L W              |
| Month         | YES       | 1-12 or JAN-DEC         | , - * /                    |
| Day of week   | YES       | 1-7 or SUN-SAT          | , - * ? / L #              |
| Year          | NO        | empty, 1970-2099        | , - * /                    |

So cron expressions can be as simple as this: `* * * * ? *`

or more complex, like this: `0/5 14,18,3-39,52 * ? JAN,MAR,SEP MON-FRI 2002-2010`

## Special Characters

- **\*** (“all values”) - used to select all values within a field. For example, “*” in the minute field means “every minute”.
- **?** (“no specific value”) - useful when you need to specify something in one of the two fields in which the character is allowed, but not the other.
- **-** - used to specify ranges. For example, “10-12” in the hour field means “the hours 10, 11 and 12”.
- **,** - used to specify additional values. For example, “MON,WED,FRI” in the day-of-week field means “the days Monday, Wednesday, and Friday”.
- **/** - used to specify increments. For example, “0/15” in the seconds field means “the seconds 0, 15, 30, and 45”.
- **L** (“last”) - has different meaning in each of the two fields in which it is allowed.
- **W** (“weekday”) - used to specify the weekday (Monday-Friday) nearest the given day.
- **#** - used to specify “the nth” XXX day of the month. For example, “6#3” means “the third Friday of the month”.

### Examples

| Expression           | Meaning |
|----------------------|---------|
| `0 0 12 * * ?`       | Fire at 12pm (noon) every day |
| `0 15 10 ? * *`      | Fire at 10:15am every day |
| `0 15 10 * * ?`      | Fire at 10:15am every day |
| `0 15 10 * * ? *`    | Fire at 10:15am every day |
| `0 15 10 * * ? 2005` | Fire at 10:15am every day during the year 2005 |
| `0 * 14 * * ?`       | Fire every minute starting at 2pm and ending at 2:59pm, every day |
| `0 0/5 14 * * ?`     | Fire every 5 minutes starting at 2pm and ending at 2:55pm, every day |
| `0 0/5 14,18 * * ?`  | Fire every 5 minutes starting at 2pm and ending at 2:55pm, AND fire every 5 minutes starting at 6pm and ending at 6:55pm, every day |
| `0 0-5 14 * * ?`     | Fire every minute starting at 2pm and ending at 2:05pm, every day |
| `0 10,44 14 ? 3 WED` | Fire at 2:10pm and at 2:44pm every Wednesday in the month of March. |
| `0 15 10 ? * MON-FRI`| Fire at 10:15am every Monday, Tuesday, Wednesday, Thursday and Friday |
| `0 15 10 15 * ?`     | Fire at 10:15am on the 15th day of every month |
| `0 15 10 L * ?`      | Fire at 10:15am on the last day of every month |
| `0 15 10 L-2 * ?`    | Fire at 10:15am on the 2nd-to-last last day of every month |
| `0 15 10 ? * 6L`     | Fire at 10:15am on the last Friday of every month |
| `0 15 10 ? * 6L 2002-2005` | Fire at 10:15am on every last friday of every month during the years 2002, 2003, 2004 and 2005 |
| `0 15 10 ? * 6#3`    | Fire at 10:15am on the third Friday of every month |
| `0 0 12 1/5 * ?`     | Fire at 12pm (noon) every 5 days every month, starting on the first day of the month. |
| `0 11 11 11 11 ?`    | Fire every November 11th at 11:11am. |
| `0 11 ? * 2,4 2024`    | Fire every Monday and Wednesday at 11:00 AM. |

### Notes

- Support for specifying both a day-of-week and a day-of-month value is not complete (you must currently use the ‘?’ character in one of these fields).
- Be careful when setting fire times between the hours of the morning when “daylight savings” changes occur in your locale.
