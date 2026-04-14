function [D] = outerDifference(a,b)
%by: Magnus Åberg
D = zeros(numel(a),numel(b));
for ib = 1:numel(b),
    for ja = 1:numel(a),
        D(ja,ib) = a(ja)-b(ib);
    end
end