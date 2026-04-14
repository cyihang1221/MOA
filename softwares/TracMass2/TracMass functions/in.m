function tf = in( values, interval )
%Magnus Åberg
a = values - interval(1);
b = values - interval(2);

tf = a .* b <= 0;